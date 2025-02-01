from typing import List, Dict
from typing_extensions import Annotated
from connectors import AzureOpenAIClient
from azure.identity import ManagedIdentityCredential, AzureCliCredential, ChainedTokenCredential
import os
import time
import logging
import requests
from .types import ColumnsRetrievalResult, ColumnItem

def columns_retrieval(
    datasource: Annotated[str, "Target datasource"],        
    table_name: Annotated[str, "Target table"],
    user_ask: Annotated[str, "The user's query or request that may influence the column retrieval"]
) -> ColumnsRetrievalResult:
    """
    Retrieves necessary columns for a specific table from the retrieval system based on the user's query to build a response.

    Args:
        datasource (str): The target datasource to filter the columns.
        table_name (str): The name of the table for which columns are to be retrieved.
        user_ask (str): The user's query or request that may influence the column retrieval.

    Returns:
        ColumnsRetrievalResult: An object containing a list of columns. Each column includes 'table_name', 'column_name', and 'description'.
    """
    aoai = AzureOpenAIClient()

    VECTOR_SEARCH_APPROACH = 'vector'
    TERM_SEARCH_APPROACH = 'term'
    HYBRID_SEARCH_APPROACH = 'hybrid'

    # Customize the search parameters
    search_index = os.getenv('AZURE_SEARCH_INDEX', 'columns')
    search_approach = os.getenv('AZURE_SEARCH_APPROACH', HYBRID_SEARCH_APPROACH)
    search_top_k = 100

    # Semantic configuration
    use_semantic = os.getenv('AZURE_SEARCH_USE_SEMANTIC', "false").lower() == "true"
    semantic_search_config = os.getenv('AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG', 'my-semantic-config')
    search_service = os.getenv('AZURE_SEARCH_SERVICE')
    search_api_version = os.getenv('AZURE_SEARCH_API_VERSION', '2024-07-01')

    search_results: List[ColumnItem] = []
    search_query = f"{user_ask} table:{table_name}"
    try:
        credential = ChainedTokenCredential(
            ManagedIdentityCredential(),
            AzureCliCredential()
        )
        start_time = time.time()
        logging.info(f"[ai_search] Generating question embeddings. Search query: {search_query}")
        embeddings_query = aoai.get_embeddings(search_query)
        response_time = round(time.time() - start_time, 2)
        logging.info(f"[ai_search] Finished generating question embeddings. {response_time} seconds")

        azureSearchKey = credential.get_token("https://search.azure.com/.default")
        azureSearchKey = azureSearchKey.token

        logging.info(f"[ai_search] Querying Azure AI Search. Search query: {search_query}")
        # Prepare the body with the desired fields and filters (table_name and datasource)
        body = {
            "select": "table_name, column_name, description",
            "filter": f"table_name eq '{table_name}' and datasource eq '{datasource}'",  # Filter by table and datasource
            "top": search_top_k
        }
        if search_approach == TERM_SEARCH_APPROACH:
            body["search"] = user_ask
        elif search_approach == VECTOR_SEARCH_APPROACH:
            body["vectorQueries"] = [{
                "kind": "vector",
                "vector": embeddings_query,
                "fields": "contentVector",
                "k": int(search_top_k)
            }]
        elif search_approach == HYBRID_SEARCH_APPROACH:
            body["search"] = user_ask
            body["vectorQueries"] = [{
                "kind": "vector",
                "vector": embeddings_query,
                "fields": "contentVector",
                "k": int(search_top_k)
            }]

        if use_semantic and search_approach != VECTOR_SEARCH_APPROACH:
            body["queryType"] = "semantic"
            body["semanticConfiguration"] = semantic_search_config

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {azureSearchKey}'
        }

        search_endpoint = f"https://{search_service}.search.windows.net/indexes/{search_index}/docs/search?api-version={search_api_version}"

        start_time = time.time()
        response = requests.post(search_endpoint, headers=headers, json=body)
        status_code = response.status_code
        text = response.text
        json_response = response.json()  # Renamed to avoid shadowing the built-in json module

        if status_code >= 400:
            error_message = f'Status code: {status_code}.'
            if text:
                error_message += f" Error: {text}."
            logging.error(f"[ai_search] Error {status_code} when searching documents. {error_message}")
        else:
            if json_response.get('value'):
                logging.info(f"[ai_search] {len(json_response['value'])} documents retrieved")
                for doc in json_response['value']:
                    # Extract the desired fields, handling missing values gracefully
                    col_table_name = doc.get('table_name', '')
                    column_name = doc.get('column_name', '')
                    description = doc.get('description', '')
                    
                    # Create a ColumnItem object and append it to search_results
                    column_item = ColumnItem(
                        table_name=col_table_name,
                        column_name=column_name,
                        description=description
                    )
                    search_results.append(column_item)
            else:
                logging.info(f"[ai_search] No documents retrieved")

        response_time = round(time.time() - start_time, 2)
        logging.info(f"[ai_search] Finished querying Azure AI Search. {response_time} seconds")

    except Exception as e:
        error_message = str(e)
        logging.error(f"[ai_search] Error when getting the answer: {error_message}")

    # Wrap the results in a ColumnsRetrievalResult and return
    return ColumnsRetrievalResult(columns=search_results)
