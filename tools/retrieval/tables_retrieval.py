from typing import List, Dict
from typing_extensions import Annotated
from connectors import AzureOpenAIClient
from azure.identity import DefaultAzureCredential
import os
import time
import logging
import requests
import json  # Import json for structured output

def tables_retrieval(
    input: Annotated[str, "A query string optimized to retrieve necessary tables from the retrieval system to construct a response to the user's request"]
) -> Annotated[List[Dict[str, str]], "A list of tables with 'table_name' and 'description' attributes"]:
    """
    Retrieves necessary tables from the retrieval system based on the input query to build a response for the user's request.

    Args:
        input (str): A query string optimized to retrieve necessary tables from the retrieval system to construct a response to the user's request.

    Returns:
        List[Dict[str, str]]: A list of dictionaries, each containing 'table_name' and 'description'.
    """
    aoai = AzureOpenAIClient()

    VECTOR_SEARCH_APPROACH = 'vector'
    TERM_SEARCH_APPROACH = 'term'
    HYBRID_SEARCH_APPROACH = 'hybrid'

    # Customize the search parameters
    search_index = os.getenv('AZURE_SEARCH_INDEX', 'tables')
    search_approach = os.getenv('AZURE_SEARCH_APPROACH', HYBRID_SEARCH_APPROACH)
    search_top_k = 20
    
    # Semantic
    use_semantic = os.getenv('AZURE_SEARCH_USE_SEMANTIC', "false").lower() == "true"
    semantic_search_config = os.getenv('AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG', 'my-semantic-config')
    search_service = os.getenv('AZURE_SEARCH_SERVICE')
    search_api_version = os.getenv('AZURE_SEARCH_API_VERSION', '2024-07-01')

    search_results: List[Dict[str, str]] = []
    search_query = input
    try:
        credential = DefaultAzureCredential()
        start_time = time.time()
        logging.info(f"[ai_search] Generating question embeddings. Search query: {search_query}")
        embeddings_query = aoai.get_embeddings(search_query)
        response_time = round(time.time() - start_time, 2)
        logging.info(f"[ai_search] Finished generating question embeddings. {response_time} seconds")

        azureSearchKey = credential.get_token("https://search.azure.com/.default")
        azureSearchKey = azureSearchKey.token

        logging.info(f"[ai_search] Querying Azure AI Search. Search query: {search_query}")
        # Prepare body with the desired fields
        body = {
            "select": "table_name, description",
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
        json_response = response.json()  # Renamed to avoid shadowing built-in json module
        if status_code >= 400:
            error_message = f'Status code: {status_code}.'
            if text:
                error_message += f" Error: {text}."
            logging.error(f"[ai_search] Error {status_code} when searching documents. {error_message}")
        else:
            if json_response.get('value'):
                logging.info(f"[ai_search] {len(json_response['value'])} documents retrieved")
                for doc in json_response['value']:
                    # Extract the desired fields, handling missing fields gracefully
                    table_name = doc.get('table_name', '')
                    description = doc.get('description', '')

                    # Append the extracted information as a dictionary
                    search_results.append({
                        "table_name": table_name,
                        "description": description
                    })
            else:
                logging.info(f"[ai_search] No documents retrieved")

        response_time = round(time.time() - start_time, 2)
        logging.info(f"[ai_search] Finished querying Azure AI Search. {response_time} seconds")

    except Exception as e:
        error_message = str(e)
        logging.error(f"[ai_search] Error when getting the answer: {error_message}")

    # Return the search_results list of dictionaries
    return search_results
