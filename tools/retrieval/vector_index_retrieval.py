from typing import Annotated, Optional, List
from connectors import AzureOpenAIClient
from azure.identity import ManagedIdentityCredential, AzureCliCredential, ChainedTokenCredential
import os
import re
import time
import logging
import requests
import json

from .types import (
    VectorIndexRetrievalResult,
    MultimodalVectorIndexRetrievalResult,
    DataPointsResult,
)


async def vector_index_retrieve(
    input: Annotated[
        str, "An optimized query string based on the user's ask and conversation history, when available"
    ],
    security_ids: str = 'anonymous'
) -> Annotated[
    VectorIndexRetrievalResult, "A Pydantic model containing the search results as a string"
]:
    """
    Performs a vector search against Azure Cognitive Search and returns the results
    wrapped in a Pydantic model. If an error occurs, the 'error' field is populated.
    """
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

    # Initialize an error placeholder
    error_message: Optional[str] = None

    try:
        credential = ChainedTokenCredential(
            ManagedIdentityCredential(),
            AzureCliCredential()
        )
        start_time = time.time()
        logging.info(f"[vector_index_retrieve] Generating question embeddings. Search query: {search_query}")
        embeddings_query = aoai.get_embeddings(search_query)
        response_time = round(time.time() - start_time, 2)
        logging.info(f"[vector_index_retrieve] Finished generating question embeddings in {response_time} seconds")

        azureSearchKey = credential.get_token("https://search.azure.com/.default").token

        logging.info(f"[vector_index_retrieve] Querying Azure Cognitive Search. Search query: {search_query}")
        # Prepare body for the search request
        body = {
            "select": "title, content, url, filepath, chunk_id",
            "top": search_top_k
        }

        # Apply the search approach
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

        # Apply security filter
        filter_str = (
            f"metadata_security_id/any(g:search.in(g, '{security_ids}')) "
            f"or not metadata_security_id/any()"
        )
        body["filter"] = filter_str
        logging.debug(f"[vector_index_retrieve] Search filter: {filter_str}")

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {azureSearchKey}'
        }

        search_endpoint = (
            f"https://{search_service}.search.windows.net/indexes/{search_index}/docs/search"
            f"?api-version={search_api_version}"
        )

        # Execute the search
        start_time = time.time()
        response = requests.post(search_endpoint, headers=headers, json=body)
        status_code = response.status_code
        response_text = response.text

        if status_code >= 400:
            # Capture the error for non-200 responses
            error_message = f"Error {status_code}: {response_text}"
            logging.error(f"[vector_index_retrieve] {error_message}")
        else:
            json_data = response.json()
            if json_data.get('value'):
                logging.info(f"[vector_index_retrieve] {len(json_data['value'])} documents retrieved")
                for doc in json_data['value']:
                    # Append file path and cleaned content
                    content_str = doc.get('content', '').strip()
                    filepath_str = doc.get('filepath', '')
                    search_results.append(f"{filepath_str}: {content_str}\n")
            else:
                logging.info("[vector_index_retrieve] No documents retrieved")

        response_time = round(time.time() - start_time, 2)
        logging.info(f"[vector_index_retrieve] Finished querying Azure Cognitive Search in {response_time} seconds")

    except Exception as e:
        error_message = f"Exception occurred: {e}"
        logging.error(f"[vector_index_retrieve] {error_message}")

    # Join the retrieved results into a single string
    sources = ' '.join(search_results)
    return VectorIndexRetrievalResult(result=sources, error=error_message)


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
    input: Annotated[
        str, "An optimized query string based on the user's ask and conversation history, when available"
    ],
    security_ids: str = 'anonymous'
) -> Annotated[
    MultimodalVectorIndexRetrievalResult,
    "A Pydantic model containing the search results with separate lists for texts and images"
]:
    """
    Variation of vector_index_retrieve that fetches text and related images from the search index.
    Returns the results wrapped in a Pydantic model with separate lists for texts and images.
    """
    aoai = AzureOpenAIClient()

    # Acquire environment variables
    search_top_k = int(os.getenv('AZURE_SEARCH_TOP_K', 3))
    search_approach = os.getenv('AZURE_SEARCH_APPROACH', 'vector')  # or 'hybrid'
    semantic_search_config = os.getenv('AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG', 'my-semantic-config')
    search_service = os.getenv('AZURE_SEARCH_SERVICE')
    search_index = os.getenv('AZURE_SEARCH_INDEX', 'ragindex')
    search_api_version = os.getenv('AZURE_SEARCH_API_VERSION', '2024-07-01')
    use_semantic = os.getenv('AZURE_SEARCH_USE_SEMANTIC', 'false').lower() == 'true'

    logging.info(f"[multimodal_vector_index_retrieve] user input: {input}")

    # Prepare lists to hold results
    text_results: List[str] = []
    image_urls: List[List[str]] = []
    
    # Initialize an error placeholder
    error_message: Optional[str] = None

    # 1. Generate embeddings for the user query
    try:
        start_time = time.time()
        embeddings_query = aoai.get_embeddings(input)
        embedding_time = round(time.time() - start_time, 2)
        logging.info(f"[multimodal_vector_index_retrieve] Query embeddings took {embedding_time} seconds")
    except Exception as e:
        error_message = f"Error generating embeddings: {e}"
        logging.error(f"[multimodal_vector_index_retrieve] {error_message}")
        # Return early with an error if embeddings fail
        return MultimodalVectorIndexRetrievalResult(
            texts=[],
            images=[],
            error=error_message
        )

    # 2. Prepare authentication
    try:
        credential = ChainedTokenCredential(ManagedIdentityCredential(), AzureCliCredential())
        azure_search_token = credential.get_token("https://search.azure.com/.default").token
    except Exception as e:
        error_message = f"Error acquiring token for Azure Search: {e}"
        logging.error(f"[multimodal_vector_index_retrieve] {error_message}")
        # Return early if token acquisition fails
        return MultimodalVectorIndexRetrievalResult(
            texts=[],
            images=[],
            error=error_message
        )

    # 3. Create the request body
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

    if use_semantic and search_approach != "vector":
        body["queryType"] = "semantic"
        body["semanticConfiguration"] = semantic_search_config

    # Apply security filter
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

    # 4. Query Azure Search
    try:
        start_time = time.time()
        resp = requests.post(search_url, headers=headers, json=body)
        response_time = round(time.time() - start_time, 2)
        logging.info(f"[multimodal_vector_index_retrieve] Finished querying Azure AI search in {response_time} seconds")

        # Check for HTTP errors
        if resp.status_code >= 400:
            error_message = f"Error {resp.status_code}: {resp.text}"
            logging.error(f"[multimodal_vector_index_retrieve] {error_message}")
        else:
            json_data = resp.json()
            for doc in json_data.get('value', []):
                # Process content and replace image filenames with URLs
                content = replace_image_filenames_with_urls(
                    doc.get('content', ''),
                    doc.get('relatedImages', [])
                )

                # Extract image URLs from content using regex
                doc_image_urls = re.findall(r'<figure>(https?://\S+)</figure>', content)
                image_urls.append(doc_image_urls)

                # Replace <figure>...</figure> with <img src="...">
                content = re.sub(r'<figure>(https?://\S+)</figure>', r'<img src="\1">', content)

                text_results.append(doc.get('filepath', '') + ": " + content.strip())
    except Exception as e:
        error_message = f"Exception in retrieval: {e}"
        logging.error(f"[multimodal_vector_index_retrieve] {error_message}")

    # 5. Return the results (with error if any)
    return MultimodalVectorIndexRetrievalResult(
        texts=text_results,
        images=image_urls,
        error=error_message
    )


def get_data_points_from_chat_log(chat_log: list) -> DataPointsResult:
    """
    Parses a chat log to extract data points (e.g., filenames with extension) from tool call events.
    Returns a Pydantic model containing the list of extracted data points.
    """
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
                    # If not JSON, remove any "images" section and treat the rest as raw text
                    texts = [re.split(r'["\']images["\']\s*:\s*\[', content_part, 1, re.IGNORECASE)[0]]

                for text in texts:
                    # Unescape characters and extract filenames
                    text = bytes(text, "utf-8").decode("unicode_escape")
                    for match in filename_pattern.findall(text):
                        extracted = match.strip(" ,\\\"").lstrip("[").rstrip("],")
                        if extracted:
                            data_points.append(extracted)

    return DataPointsResult(data_points=data_points)
