from typing_extensions import Annotated
from connectors import AzureOpenAIClient
from azure.identity import ManagedIdentityCredential, AzureCliCredential, ChainedTokenCredential
import os
import time
import logging
import requests

def vector_index_retrieve(
    input: Annotated[str, "An optimized query string based on the user's ask and conversation history, when available"],
    security_ids: str = 'anonymous'
) -> Annotated[str, "The output is a string with the search results"]:
    aoai = AzureOpenAIClient()

    search_top_k = os.getenv('AZURE_SEARCH_TOP_K', 3)
    search_approach = os.getenv('AZURE_SEARCH_APPROACH', 'hybrid')
    semantic_search_config = os.getenv('AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG', 'my-semantic-config')
    search_service = os.getenv('AZURE_SEARCH_SERVICE')
    search_index = os.getenv('AZURE_SEARCH_INDEX', 'ragindex')	
    search_api_version = os.getenv('AZURE_SEARCH_API_VERSION', '2024-07-01')
    use_semantic = os.getenv('AZURE_SEARCH_USE_SEMANTIC', 'false').lower() == 'true'

    VECTOR_SEARCH_APPROACH = 'vector'
    TERM_SEARCH_APPROACH = 'term'
    HYBRID_SEARCH_APPROACH = 'hybrid'

    search_results = []
    search_query = input
    try:
        credential = ChainedTokenCredential(
                ManagedIdentityCredential(),
                AzureCliCredential()
            )
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

        filter_str = (
            f"metadata_security_id/any(g:search.in(g, '{security_ids}')) "
            f"or not metadata_security_id/any()"
        )
        body["filter"] = filter_str

        logging.debug(f"[ai_search] search filter: {filter_str}")

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
            logging.error(f"[multimodal_retrieve] error {response.status_code}: {response.text}")
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

def replace_image_filenames_with_urls(content: str, related_images: list) -> str:
    """
    Replace image filenames in the content string with their corresponding URLs from the related_images list.
    """
    for image_url in related_images:
        # Extract the filename from the URL
        image_filename = image_url.split('/')[-1]
        # Replace occurrences of the filename in the content with the URL
        content = content.replace(image_filename, image_url)
    return content

def multimodal_vector_index_retrieve(
    input: Annotated[str, "An optimized query string based on the user's ask and conversation history, when available"],
    security_ids: str = 'anonymous'
) -> Annotated[str, "The output is a string with the search results containing retrieved documents including text and images"]:
    """
    Variation of vector_index_retrieve that fetches text + related images from the search index
    """
    aoai = AzureOpenAIClient()

    # Acquire your environment variables
    search_top_k = int(os.getenv('AZURE_SEARCH_TOP_K', 3))
    search_approach = os.getenv('AZURE_SEARCH_APPROACH', 'vector')  # or 'hybrid'
    semantic_search_config = os.getenv('AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG', 'my-semantic-config')
    search_service = os.getenv('AZURE_SEARCH_SERVICE')
    search_index = os.getenv('AZURE_SEARCH_INDEX', 'ragindex')	
    search_api_version = os.getenv('AZURE_SEARCH_API_VERSION', '2024-07-01')
    use_semantic = (os.getenv('AZURE_SEARCH_USE_SEMANTIC', 'false').lower() == 'true')

    logging.info(f"[multimodal_retrieve] user input: {input}")

    # 1. Generate embeddings for the user query
    start_time = time.time()
    embeddings_query = aoai.get_embeddings(input)
    embedding_time = round(time.time() - start_time, 2)
    logging.info(f"[multimodal_retrieve] Query embeddings took {embedding_time} seconds")

    # Prepare authentication
    credential = ChainedTokenCredential(ManagedIdentityCredential(), AzureCliCredential())
    azure_search_token = credential.get_token("https://search.azure.com/.default").token

    # 2. Create the request body
    body = {
        "select": "title, content, filepath, relatedImages",
        "top": search_top_k,
        "vectorQueries": [
            {
                "kind": "vector",
                "vector": embeddings_query,
                "fields": "contentVector",
                "k": int(search_top_k)
            },
            {
                "kind": "vector",
                "vector": embeddings_query,
                "fields": "captionVector",
                "k": int(search_top_k)
            }
        ]
    }

    # If you want semantic search layering on top of vector, adjust below
    if use_semantic and search_approach != "vector":
        body["queryType"] = "semantic"
        body["semanticConfiguration"] = semantic_search_config

    # Restrict results by security filters (if any).
    filter_str = (
        f"metadata_security_id/any(g:search.in(g, '{security_ids}')) "
        "or not metadata_security_id/any()"
    )
    body["filter"] = filter_str

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {azure_search_token}'
    }

    search_url = (
        f"https://{search_service}.search.windows.net"
        f"/indexes/{search_index}/docs/search"
        f"?api-version={search_api_version}"
    )

    search_results = []
    try:
        start_time = time.time()
        resp = requests.post(search_url, headers=headers, json=body)
        response_time = round(time.time() - start_time, 2)
        logging.info(f"[multimodal_retrieve] Finished querying Azure AI search. {response_time} seconds")
        
        if resp.status_code >= 400:
            logging.error(f"[multimodal_retrieve] error {resp.status_code}: {resp.text}")
        else:
            json_data = resp.json()
            for doc in json_data.get('value', []):
                doc['content'] = replace_image_filenames_with_urls(doc['content'], doc.get('relatedImages', []))
                search_results.append(doc['filepath'] + ": " + doc['content'].strip() + "\n")
    except Exception as e:
        logging.error(f"[multimodal_retrieve] Exception in retrieval: {e}")

    # Return a JSON string
    sources = ' '.join(search_results)
    return sources
