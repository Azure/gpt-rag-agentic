from typing_extensions import Annotated
from connectors import AzureOpenAIClient
from azure.identity import DefaultAzureCredential
import os
import time
import logging
import requests

def vector_index_retrieve(
    input: Annotated[str, "The user question"]
) -> Annotated[str, "The output is a string with the search results"]:
    aoai = AzureOpenAIClient()

    search_top_k = os.getenv('AZURE_SEARCH_TOP_K', 3)
    search_approach = os.getenv('AZURE_SEARCH_APPROACH', 'hybrid')
    use_semantic = os.getenv('AZURE_SEARCH_USE_SEMANTIC', False)
    semantic_search_config = os.getenv('AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG', 'my-semantic-config')
    search_service = os.getenv('AZURE_SEARCH_SERVICE')
    search_index = os.getenv('AZURE_SEARCH_INDEX', 'ragindex')	
    search_api_version = os.getenv('AZURE_SEARCH_API_VERSION', '2024-07-01')

    VECTOR_SEARCH_APPROACH = 'vector'
    TERM_SEARCH_APPROACH = 'term'
    HYBRID_SEARCH_APPROACH = 'hybrid'

    search_results = []
    search_query = input
    try:
        credential = DefaultAzureCredential()
        start_time = time.time()
        logging.info(f"[ai_search] generating question embeddings. search query: {search_query}")
        embeddings_query = aoai.get_embeddings(search_query)
        response_time = round(time.time() - start_time, 2)
        logging.info(f"[ai_search] finished generating question embeddings. {response_time} seconds")
        azureSearchKey = credential.get_token("https://search.azure.com/.default")
        azureSearchKey = azureSearchKey.token

        logging.info(f"[ai_search] querying azure ai search. search query: {search_query}")
        # prepare body
        body = {
            "select": "title, content, url, filepath, chunk_id",
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

        if use_semantic == "true" and search_approach != VECTOR_SEARCH_APPROACH:
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
        json =response.json()    
        if status_code >= 400:
            error_message = f'Status code: {status_code}.'
            if text != "":
                error_message += f" Error: {text}."
            logging.error(f"[ai_search] error {status_code} when searching documents. {error_message}")
        else:
            if json['value']:
                logging.info(f"[ai_search] {len(json['value'])} documents retrieved")
                for doc in json['value']:
                    search_results.append(doc['filepath'] + ": " + doc['content'].strip() + "\n")
            else:
                logging.info(f"[ai_search] No documents retrieved")

        response_time = round(time.time() - start_time, 2)
        logging.info(f"[ai_search] finished querying azure ai search. {response_time} seconds")

    except Exception as e:
        error_message = str(e)
        logging.error(f"[ai_search] error when getting the answer {error_message}")

    sources =  ' '.join(search_results)
    return sources

