from typing_extensions import Annotated
from connectors import AzureOpenAIClient
from azure.identity import ManagedIdentityCredential, AzureCliCredential, ChainedTokenCredential
import os
import re
import time
import logging
import requests
import json

async def vector_index_retrieve(
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
        logging.info(f"[vector_index_retrieve] generating question embeddings. search query: {search_query}")
        embeddings_query = aoai.get_embeddings(search_query)
        response_time = round(time.time() - start_time, 2)
        logging.info(f"[vector_index_retrieve] finished generating question embeddings. {response_time} seconds")
        azureSearchKey = credential.get_token("https://search.azure.com/.default")
        azureSearchKey = azureSearchKey.token

        logging.info(f"[vector_index_retrieve] querying azure ai search. search query: {search_query}")
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

        logging.debug(f"[vector_index_retrieve] search filter: {filter_str}")

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
            logging.error(f"[vector_index_retrieve] error {response.status_code}: {response.text}")
        else:
            if json['value']:
                logging.info(f"[vector_index_retrieve] {len(json['value'])} documents retrieved")
                for doc in json['value']:
                    search_results.append(doc['filepath'] + ": " + doc['content'].strip() + "\n")
            else:
                logging.info(f"[vector_index_retrieve] No documents retrieved")

        response_time = round(time.time() - start_time, 2)
        logging.info(f"[vector_index_retrieve] finished querying azure ai search. {response_time} seconds")

    except Exception as e:
        error_message = str(e)
        logging.error(f"[vector_index_retrieve] error when getting the answer {error_message}")

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

async def multimodal_vector_index_retrieve(
    input: Annotated[str, "An optimized query string based on the user's ask and conversation history, when available"],
    security_ids: str = 'anonymous'
) -> Annotated[str, "The output is a string with the search results containing retrieved documents including text and images"]:
    """
    Variation of vector_index_retrieve that fetches text + related images from the search index
    Returns a dictionary with separate lists for text snippets and image URLs.
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

    logging.info(f"[multimodal_vector_index_retrieve] user input: {input}")

    # 1. Generate embeddings for the user query
    start_time = time.time()
    embeddings_query = aoai.get_embeddings(input)
    embedding_time = round(time.time() - start_time, 2)
    logging.info(f"[multimodal_vector_index_retrieve] Query embeddings took {embedding_time} seconds")

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

    text_results = []
    image_urls = []
    try:
        start_time = time.time()
        resp = requests.post(search_url, headers=headers, json=body)
        response_time = round(time.time() - start_time, 2)
        logging.info(f"[multimodal_vector_index_retrieve] Finished querying Azure AI search. {response_time} seconds")
        
        if resp.status_code >= 400:
            logging.error(f"[multimodal_vector_index_retrieve] error {resp.status_code}: {resp.text}")
        else:
            json_data = resp.json()
            for doc in json_data.get('value', []):
                # Extract and process content
                content = replace_image_filenames_with_urls(doc.get('content', ''), doc.get('relatedImages', []))
                
                # Extract image URLs
                doc_image_urls = re.findall(r'<figure>(https?://\S+)</figure>', content)
                image_urls.append(doc_image_urls)

                # Replace <figure>http://domain.com</figure> pattern by <img src="http://domain.com">
                content = re.sub(r'<figure>(https?://\S+)</figure>', r'<img src="\1">', content)                

                text_results.append(doc.get('filepath', '') + ": " + content.strip())     
    except Exception as e:
        logging.error(f"[multimodal_vector_index_retrieve] Exception in retrieval: {e}")

    return json.dumps({
        "texts": text_results,
        "images": image_urls
    })


def get_data_points_from_chat_log(chat_log: list) -> list:
    # Regex patterns
    request_call_id_pattern = re.compile(r"id='([^']+)'")
    request_function_name_pattern = re.compile(r"name='([^']+)'")
    exec_call_id_pattern = re.compile(r"call_id='([^']+)'")
    exec_content_pattern = re.compile(r"content='(.+?)', call_id=", re.DOTALL)
    
    # Allowed file extensions
    allowed_extensions = ['vtt', 'xlsx', 'xls', 'pdf', 'docx', 'pptx', 'png', 'jpeg', 'jpg', 'bmp', 'tiff']
    
    # Filename pattern: matches "filename.ext: ..." until the next filename or end of string
    filename_pattern = re.compile(
        rf"([^\s:]+\.(?:{'|'.join(allowed_extensions)})\s*:\s*.*?)(?=[^\s:]+\.(?:{'|'.join(allowed_extensions)})\s*:|$)",
        re.IGNORECASE | re.DOTALL
    )

    relevant_call_ids = set()
    data_points = []

    for msg in chat_log:
        if msg["message_type"] == "ToolCallRequestEvent":
            # Check if this request is for 'vector_index_retrieve_wrapper'
            content = msg["content"][0]
            call_id_match = request_call_id_pattern.search(content)
            function_name_match = request_function_name_pattern.search(content)
            if call_id_match and function_name_match:
                if function_name_match.group(1) == "vector_index_retrieve_wrapper":
                    relevant_call_ids.add(call_id_match.group(1))

        elif msg["message_type"] == "ToolCallExecutionEvent":
            # If this execution corresponds to a relevant call_id, parse filenames
            content = msg["content"][0]
            call_id_match = exec_call_id_pattern.search(content)
            if call_id_match and call_id_match.group(1) in relevant_call_ids:
                content_part_match = exec_content_pattern.search(content)
                if not content_part_match:
                    continue
                content_part = content_part_match.group(1)

                # Try parsing as JSON first
                try:
                    parsed = json.loads(content_part)
                    texts = parsed.get("texts", [])
                except json.JSONDecodeError:
                    # If not JSON, strip out any "images" section and treat the rest as raw text
                    texts = [re.split(r'["\']images["\']\s*:\s*\[', content_part, 1, re.IGNORECASE)[0]]

                for text in texts:
                    # Unescape characters and extract filenames
                    text = bytes(text, "utf-8").decode("unicode_escape")
                    for match in filename_pattern.findall(text):
                        extracted = match.strip(" ,\\\"").lstrip("[").rstrip("],")
                        if extracted:
                            data_points.append(extracted)
                            
    return data_points