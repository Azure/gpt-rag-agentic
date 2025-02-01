import logging 
import os
import requests
import time
from typing import List, Optional, Annotated

from azure.identity import ChainedTokenCredential, ManagedIdentityCredential, AzureCliCredential
from connectors import AzureOpenAIClient

from .types import TablesRetrievalResult, TableRetrievalItem

def tables_retrieval(
    datasource: Annotated[str, "Target datasource"],
    input: Annotated[str, "A query string optimized to retrieve necessary tables from the retrieval system to construct a response to the user's request"]
) -> TablesRetrievalResult:
    """
    Retrieves necessary tables from the retrieval system based on the input query to build a response for the user's request.

    Args:
        datasource (str): The target datasource to filter the tables.
        input (str): A query string optimized to retrieve necessary tables from the retrieval system to construct a response.

    Returns:
        TablesRetrievalResult: An object containing a list of tables. Each table includes 'table_name' and 'description'.
                               If an error occurs, the 'error' field is populated.
    """
    aoai = AzureOpenAIClient()

    VECTOR_SEARCH_APPROACH = 'vector'
    TERM_SEARCH_APPROACH = 'term'
    HYBRID_SEARCH_APPROACH = 'hybrid'

    search_index = os.getenv('NL2SQL_TABLES_INDEX', 'nl2sql-tables')
    search_approach = os.getenv('AZURE_SEARCH_APPROACH', HYBRID_SEARCH_APPROACH)
    search_top_k = 20

    use_semantic = os.getenv('AZURE_SEARCH_USE_SEMANTIC', "false").lower() == "true"
    semantic_search_config = os.getenv('AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG', 'my-semantic-config')
    search_service = os.getenv('AZURE_SEARCH_SERVICE')
    search_api_version = os.getenv('AZURE_SEARCH_API_VERSION', '2024-07-01')

    search_results: List[TableRetrievalItem] = []
    search_query = input
    error_message: Optional[str] = None  # Initialize an error placeholder

    try:
        credential = ChainedTokenCredential(
            ManagedIdentityCredential(),
            AzureCliCredential()
        )

        start_time = time.time()
        logging.info(f"[ai_search] Generating question embeddings. Search query: {search_query}")
        embeddings_query = aoai.get_embeddings(search_query)
        response_time = round(time.time() - start_time, 2)
        logging.info(f"[ai_search] Finished generating question embeddings in {response_time} seconds")

        azure_search_key = credential.get_token("https://search.azure.com/.default").token

        logging.info(f"[ai_search] Querying Azure AI Search. Search query: {search_query}")

        # Prepare request body
        body = {
            "select": "table_name, description",
            "filter": f"datasource eq '{datasource}'",
            "top": search_top_k
        }
        if search_approach == TERM_SEARCH_APPROACH:
            body["search"] = search_query
        elif search_approach == VECTOR_SEARCH_APPROACH:
            body["vectorQueries"] = [{
                "kind": "vector",
                "vector": embeddings_query,
                "fields": "contentVector",
                "k": int(search_top_k)
            }]
        elif search_approach == HYBRID_SEARCH_APPROACH:
            body["search"] = search_query
            body["vectorQueries"] = [{
                "kind": "vector",
                "vector": embeddings_query,
                "fields": "contentVector",
                "k": int(search_top_k)
            }]

        # If semantic search is enabled and we're not using vector-only
        if use_semantic and search_approach != VECTOR_SEARCH_APPROACH:
            body["queryType"] = "semantic"
            body["semanticConfiguration"] = semantic_search_config

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {azure_search_key}"
        }

        search_endpoint = (
            f"https://{search_service}.search.windows.net/"
            f"indexes/{search_index}/docs/search?api-version={search_api_version}"
        )

        start_time = time.time()
        response = requests.post(search_endpoint, headers=headers, json=body)
        status_code = response.status_code
        text = response.text
        json_response = response.json()

        if status_code >= 400:
            # Capture the error if the response is not successful
            error_message = f"Status code: {status_code}."
            if text:
                error_message += f" Error: {text}."
            logging.error(f"[ai_search] Error {status_code} when searching documents. {error_message}")
        else:
            if json_response.get("value"):
                logging.info(f"[ai_search] {len(json_response['value'])} documents retrieved")
                for doc in json_response["value"]:
                    table_name = doc.get("table_name", "")
                    description = doc.get("description", "")

                    # Append a TableRetrievalItem
                    search_results.append(TableRetrievalItem(
                        table_name=table_name,
                        description=description
                    ))
            else:
                logging.info("[ai_search] No documents retrieved")

        response_time = round(time.time() - start_time, 2)
        logging.info(f"[ai_search] Finished querying Azure AI Search in {response_time} seconds")

    except Exception as e:
        # Capture any exceptions
        error_message = str(e)
        logging.error(f"[ai_search] Error when retrieving tables: {error_message}")

    # Return with any error captured
    return TablesRetrievalResult(tables=search_results, error=error_message)
