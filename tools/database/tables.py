import os
import time
import logging
import asyncio
from typing import Any, Dict, Annotated, Optional, List

import aiohttp
from azure.identity import ChainedTokenCredential, ManagedIdentityCredential, AzureCliCredential

# Import Pydantic models from your types file.
from .types import (
    TablesList, TableItem, SchemaInfo,
    TablesRetrievalResult, TableRetrievalItem
)
# Import the AzureOpenAIClient for generating embeddings.
from connectors import AzureOpenAIClient


# -----------------------------------------------------------------------------
# Helper function to perform the Azure AI Search query using aiohttp
# -----------------------------------------------------------------------------
async def _perform_search(body: Dict[str, Any], search_index: str) -> Dict[str, Any]:
    """
    Executes a search query against the specified Azure AI Search index.

    Args:
        body (dict): The JSON body for the search request.
        search_index (str): The name of the search index to query.

    Returns:
        dict: The JSON response from the search service.

    Raises:
        Exception: If the search query fails or an error occurs obtaining the token.
    """
    search_service = os.getenv("AZURE_SEARCH_SERVICE")
    if not search_service:
        raise Exception("AZURE_SEARCH_SERVICE environment variable is not set.")
    search_api_version = os.getenv("AZURE_SEARCH_API_VERSION", "2024-07-01")

    # Build the search endpoint URL.
    search_endpoint = (
        f"https://{search_service}.search.windows.net/indexes/{search_index}/docs/search"
        f"?api-version={search_api_version}"
    )

    # Obtain an access token for the search service.
    try:
        credential = ChainedTokenCredential(
            ManagedIdentityCredential(),
            AzureCliCredential()
        )
        azure_search_scope = "https://search.azure.com/.default"
        token = credential.get_token(azure_search_scope).token
    except Exception as e:
        logging.error("Error obtaining Azure Search token.", exc_info=True)
        raise Exception("Failed to obtain Azure Search token.") from e

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    # Perform the asynchronous HTTP POST request.
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(search_endpoint, headers=headers, json=body) as response:
                if response.status >= 400:
                    text = await response.text()
                    error_message = f"Status code: {response.status}. Error: {text}"
                    logging.error(f"[tables] {error_message}")
                    raise Exception(error_message)
                result = await response.json()
                return result
        except Exception as e:
            logging.error("Error during the search HTTP request.", exc_info=True)
            raise Exception("Failed to execute search query.") from e


# -----------------------------------------------------------------------------
# Function to retrieve all tables info from the Azure AI Search index
# -----------------------------------------------------------------------------
async def get_all_tables_info(
    datasource: Annotated[str, "Name of the target datasource"]
) -> TablesList:
    """
    Retrieve a list of tables filtering by the given datasource.
    Each entry will have "table", "description", and "datasource".

    Returns:
        TablesList: Contains a list of TableItem objects and an optional error message.
    """
    search_index = "nl2sql-tables"
    safe_datasource = datasource.replace("'", "''")
    filter_expression = f"datasource eq '{safe_datasource}'"

    body = {
        "search": "*",
        "filter": filter_expression,
        "select": "table, description, datasource",
        "top": 1000  # Adjust based on your expected document count.
    }

    logging.info(f"[tables] Querying Azure AI Search for tables in datasource '{datasource}'")
    tables_info: List[TableItem] = []
    error_message: Optional[str] = None

    try:
        start_time = time.time()
        result = await _perform_search(body, search_index)
        elapsed = round(time.time() - start_time, 2)
        logging.info(f"[tables] Finished querying tables in {elapsed} seconds")

        for doc in result.get("value", []):
            table_item = TableItem(
                table=doc.get("table", ""),
                description=doc.get("description", ""),
                datasource=doc.get("datasource", "")
            )
            tables_info.append(table_item)
    except Exception as e:
        error_message = str(e)
        logging.error(f"[tables] Error querying tables: {error_message}")

    if not tables_info:
        return TablesList(
            tables=[],
            error=f"No datasource with name '{datasource}' was found. {error_message or ''}".strip()
        )

    return TablesList(tables=tables_info, error=error_message)


# -----------------------------------------------------------------------------
# Function to retrieve schema information for a given table from the index
# -----------------------------------------------------------------------------
async def get_schema_info(
    datasource: Annotated[str, "Target datasource"],
    table_name: Annotated[str, "Target table"]
) -> SchemaInfo:
    """
    Retrieve schema information for a specific table in a given datasource.
    Returns the table's description and its columns.

    Returns:
        SchemaInfo: Contains the schema details or an error message.
    """
    search_index = "nl2sql-tables"
    safe_datasource = datasource.replace("'", "''")
    safe_table_name = table_name.replace("'", "''")
    filter_expression = f"datasource eq '{safe_datasource}' and table eq '{safe_table_name}'"

    body = {
        "search": "*",
        "filter": filter_expression,
        "select": "table, description, datasource, columns",
        "top": 1
    }

    logging.info(f"[tables] Querying Azure AI Search for schema info for table '{table_name}' in datasource '{datasource}'")
    error_message: Optional[str] = None

    try:
        start_time = time.time()
        result = await _perform_search(body, search_index)
        elapsed = round(time.time() - start_time, 2)
        logging.info(f"[tables] Finished querying schema info in {elapsed} seconds")

        docs = result.get("value", [])
        if not docs:
            error_message = f"Table '{table_name}' not found in datasource '{datasource}'."
            return SchemaInfo(
                datasource=datasource,
                table=table,
                error=error_message,
                columns=None
            )

        doc = docs[0]
        columns_data = doc.get("columns", [])
        columns: Dict[str, str] = {}
        if isinstance(columns_data, list):
            for col in columns_data:
                col_name = col.get("name")
                col_description = col.get("description", "")
                if col_name:
                    columns[col_name] = col_description

        return SchemaInfo(
            datasource=datasource,
            table=doc.get("table", table_name),
            description=doc.get("description", ""),
            columns=columns
        )
    except Exception as e:
        error_message = str(e)
        logging.error(f"[tables] Error querying schema info: {error_message}")
        return SchemaInfo(
            datasource=datasource,
            table=table_name,
            error=error_message,
            columns=None
        )


# ---------------------------------------------------------------------------
# Function to retrieve necessary tables from the retrieval system
# based on an optimized input query, to construct a response to the user's request.
# ---------------------------------------------------------------------------
async def tables_retrieval(
    input: Annotated[str, "A query string optimized to retrieve necessary tables from the retrieval system to construct a response"],
    datasource: Annotated[Optional[str], "Target datasource"] = None
) -> TablesRetrievalResult:
    """
    Retrieves necessary tables from the retrieval system based on the input query.

    Returns:
        TablesRetrievalResult: An object containing a list of TableRetrievalItem objects.
                               If an error occurs, the 'error' field is populated.
    """
    # Read search configuration from environment variables.
    search_index = os.getenv("NL2SQL_TABLES_INDEX", "nl2sql-tables")
    search_approach = os.getenv("AZURE_SEARCH_APPROACH", "hybrid")
    search_top_k = 10
    use_semantic = os.getenv("AZURE_SEARCH_USE_SEMANTIC", "false").lower() == "true"
    semantic_search_config = os.getenv("AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG", "my-semantic-config")

    search_query = input  # The optimized query string.
    search_results: List[TableRetrievalItem] = []
    error_message: Optional[str] = None

    try:
        # Generate embeddings for the search query using the Azure OpenAI Client.
        aoai = AzureOpenAIClient()
        logging.info(f"[tables] Generating question embeddings. Search query: {search_query}")
        embeddings_query = await asyncio.to_thread(aoai.get_embeddings, search_query)
        logging.info("[tables] Finished generating question embeddings.")

        # Prepare the request body.
        body: Dict[str, Any] = {
            "select": "table, description",
            "top": search_top_k
        }
        # Apply datasource filter if provided.
        if datasource:
            body["filter"] = f"datasource eq '{datasource}'"

        # Adjust the body based on the search approach.
        if search_approach.lower() == "term":
            body["search"] = search_query
        elif search_approach.lower() == "vector":
            body["vectorQueries"] = [{
                "kind": "vector",
                "vector": embeddings_query,
                "fields": "contentVector",
                "k": int(search_top_k)
            }]
        elif search_approach.lower() == "hybrid":
            body["search"] = search_query
            body["vectorQueries"] = [{
                "kind": "vector",
                "vector": embeddings_query,
                "fields": "contentVector",
                "k": int(search_top_k)
            }]

        # If semantic search is enabled and we're not using vector-only search.
        if use_semantic and search_approach.lower() != "vector":
            body["queryType"] = "semantic"
            body["semanticConfiguration"] = semantic_search_config

        logging.info(f"[tables] Querying Azure AI Search for tables. Search query: {search_query}")
        start_time = time.time()
        result = await _perform_search(body, search_index)
        elapsed = round(time.time() - start_time, 2)
        logging.info(f"[tables] Finished querying Azure AI Search in {elapsed} seconds")

        # Process the returned documents.
        if result.get("value"):
            logging.info(f"[tables] {len(result['value'])} documents retrieved")
            for doc in result["value"]:
                table_name = doc.get("table", "")
                description = doc.get("description", "")
                search_results.append(TableRetrievalItem(
                    table=table_name,
                    description=description,
                    datasource=datasource
                ))
        else:
            logging.info("[tables] No documents retrieved")
    except Exception as e:
        error_message = str(e)
        logging.error(f"[tables] Error when retrieving tables: {error_message}")

    return TablesRetrievalResult(tables=search_results, error=error_message)
