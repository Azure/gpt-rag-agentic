import os
import re
import time
import json
import logging
import asyncio
from typing import Annotated, Optional, List, Dict, Any
from urllib.parse import urlparse

import aiohttp
from azure.identity import ManagedIdentityCredential, AzureCliCredential, ChainedTokenCredential
from connectors import AzureOpenAIClient

from .types import (
    VectorIndexRetrievalResult,
    MultimodalVectorIndexRetrievalResult,
    DataPointsResult,
)

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

async def _get_azure_search_token() -> str:
    """
    Acquires an Azure Search access token using chained credentials.
    """
    try:
        credential = ChainedTokenCredential(
            ManagedIdentityCredential(),
            AzureCliCredential()
        )
        # Wrap the synchronous token acquisition in a thread.
        token_obj = await asyncio.to_thread(credential.get_token, "https://search.azure.com/.default")
        return token_obj.token
    except Exception as e:
        logging.error("Error obtaining Azure Search token.", exc_info=True)
        raise Exception("Failed to obtain Azure Search token.") from e


async def _perform_search(url: str, headers: Dict[str, str], body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Performs an asynchronous HTTP POST request to the given URL with the provided headers and body.
    Returns the parsed JSON response.

    Raises:
        Exception: When the request fails or returns an error status.
    """
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=body) as response:
                if response.status >= 400:
                    text = await response.text()
                    error_message = f"Error {response.status}: {text}"
                    logging.error(f"[_perform_search] {error_message}")
                    raise Exception(error_message)
                return await response.json()
        except Exception as e:
            logging.error("Error during asynchronous HTTP request.", exc_info=True)
            raise Exception("Failed to execute search query.") from e


# -----------------------------------------------------------------------------
# Main Functions
# -----------------------------------------------------------------------------

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

    search_results: List[str] = []
    error_message: Optional[str] = None
    search_query = input

    try:
        # Generate embeddings for the query.
        start_time = time.time()
        logging.info(f"[vector_index_retrieve] Generating question embeddings. Search query: {search_query}")
        # Wrap synchronous get_embeddings in a thread.
        embeddings_query = await asyncio.to_thread(aoai.get_embeddings, search_query)
        response_time = round(time.time() - start_time, 2)
        logging.info(f"[vector_index_retrieve] Finished generating embeddings in {response_time} seconds")

        # Acquire token for Azure Search.
        azure_search_token = await _get_azure_search_token()

        # Prepare the request body.
        body: Dict[str, Any] = {
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

        # Apply security filter.
        filter_str = (
            f"metadata_security_id/any(g:search.in(g, '{security_ids}')) "
            f"or not metadata_security_id/any()"
        )
        body["filter"] = filter_str
        logging.debug(f"[vector_index_retrieve] Search filter: {filter_str}")

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {azure_search_token}'
        }

        search_url = (
            f"https://{search_service}.search.windows.net/indexes/{search_index}/docs/search"
            f"?api-version={search_api_version}"
        )

        # Execute the search query asynchronously.
        start_time = time.time()
        response_json = await _perform_search(search_url, headers, body)
        elapsed = round(time.time() - start_time, 2)
        logging.info(f"[vector_index_retrieve] Finished querying Azure Cognitive Search in {elapsed} seconds")

        if response_json.get('value'):
            logging.info(f"[vector_index_retrieve] {len(response_json['value'])} documents retrieved")
            for doc in response_json['value']:
                content_str = doc.get('content', '').strip()
                url = doc.get('url', '')
                url = re.sub(r'https://[^/]+\.blob\.core\.windows\.net', '', url)
                search_results.append(f"{url}: {content_str}\n")
        else:
            logging.info("[vector_index_retrieve] No documents retrieved")

    except Exception as e:
        error_message = f"Exception occurred: {e}"
        logging.error(f"[vector_index_retrieve] {error_message}", exc_info=True)

    # Join the retrieved results into a single string.
    sources = ' '.join(search_results)
    return VectorIndexRetrievalResult(result=sources, error=error_message)


def replace_image_filenames_with_urls(content: str, related_images: list) -> str:
    """
    Replace image filenames or relative paths in the content string with their corresponding full URLs
    from the related_images list.
    """
    for image_url in related_images:
        # Parse the URL and remove the leading slash from the path
        parsed_url = urlparse(image_url)
        image_path = parsed_url.path.lstrip('/')  # e.g., 'documents-images/myfolder/filename.png'

        # Replace occurrences of the relative path in the content with the full URL
        content = content.replace(image_path, image_url)

        # Also replace only the filename if it appears alone
        # filename = image_path.split('/')[-1]
        # content = content.replace(filename, image_url)

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
    search_top_k = int(os.getenv('AZURE_SEARCH_TOP_K', 3))
    search_approach = os.getenv('AZURE_SEARCH_APPROACH', 'vector')  # or 'hybrid'
    semantic_search_config = os.getenv('AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG', 'my-semantic-config')
    search_service = os.getenv('AZURE_SEARCH_SERVICE')
    search_index = os.getenv('AZURE_SEARCH_INDEX', 'ragindex')
    search_api_version = os.getenv('AZURE_SEARCH_API_VERSION', '2024-07-01')
    use_semantic = os.getenv('AZURE_SEARCH_USE_SEMANTIC', 'false').lower() == 'true'

    logging.info(f"[multimodal_vector_index_retrieve] User input: {input}")

    text_results: List[str] = []
    image_urls: List[List[str]] = []
    image_captions: List[str] = []
    error_message: Optional[str] = None

    # 1. Generate embeddings for the query.
    try:
        start_time = time.time()
        embeddings_query = await asyncio.to_thread(aoai.get_embeddings, input)
        embedding_time = round(time.time() - start_time, 2)
        logging.info(f"[multimodal_vector_index_retrieve] Query embeddings took {embedding_time} seconds")
    except Exception as e:
        error_message = f"Error generating embeddings: {e}"
        logging.error(f"[multimodal_vector_index_retrieve] {error_message}", exc_info=True)
        return MultimodalVectorIndexRetrievalResult(
            texts=[],
            images=[],
            error=error_message
        )

    # 2. Acquire Azure Search token.
    try:
        azure_search_token = await _get_azure_search_token()
    except Exception as e:
        error_message = f"Error acquiring token for Azure Search: {e}"
        logging.error(f"[multimodal_vector_index_retrieve] {error_message}", exc_info=True)
        return MultimodalVectorIndexRetrievalResult(
            texts=[],
            images=[],
            error=error_message
        )

    # 3. Build the request body.
    body: Dict[str, Any] = {
        "select": "title, content, filepath, url, imageCaptions, relatedImages",
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

    # Apply security filter.
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

    # 4. Query Azure Search.
    try:
        start_time = time.time()
        response_json = await _perform_search(search_url, headers, body)
        response_time = round(time.time() - start_time, 2)
        logging.info(f"[multimodal_vector_index_retrieve] Finished querying Azure AI Search in {response_time} seconds")

        for doc in response_json.get('value', []):
            
            content = doc.get('content', '')
            url = doc.get('url', '')
            captions = doc.get('imageCaptions', '')
            image_captions.append(captions)

            # Convert blob URL to relative path
            url = re.sub(r'https://[^/]+\.blob\.core\.windows\.net', '', url)
            text_results.append(f"{url}: {content.strip()}")

            # Replace image filenames with URLs
            content = replace_image_filenames_with_urls(content, doc.get('relatedImages', []))

            # Extract image URLs from <figure> tags
            doc_image_urls = re.findall(r'<figure>(https?://.*?)</figure>', content)
            # doc_image_urls = [
            #     re.sub(r'https://[^/]+\.blob\.core\.windows\.net', '', img_url)
            #     for img_url in doc_image_urls
            # ]
            image_urls.append(doc_image_urls)

            # Replace <figure>...</figure> with <img src="...">
            content = re.sub(r'<figure>(https?://\S+)</figure>', r'<img src="\1">', content)

    except Exception as e:
        error_message = f"Exception in retrieval: {e}"
        logging.error(f"[multimodal_vector_index_retrieve] {error_message}", exc_info=True)

    return MultimodalVectorIndexRetrievalResult(
        texts=text_results,
        captions=image_captions,        
        images=image_urls,
        error=error_message
    )


def get_data_points_from_chat_log(chat_log: list) -> DataPointsResult:
    """
    Parses a chat log to extract data points (e.g., filenames with extension) from tool call events.
    Returns a Pydantic model containing the list of extracted data points.
    """
    # Regex patterns.
    request_call_id_pattern = re.compile(r"id='([^']+)'")
    request_function_name_pattern = re.compile(r"name='([^']+)'")
    exec_call_id_pattern = re.compile(r"call_id='([^']+)'")
    exec_content_pattern = re.compile(r"content='(.+?)', call_id=", re.DOTALL)

    # Allowed file extensions.
    allowed_extensions = ['vtt', 'xlsx', 'xls', 'pdf', 'docx', 'pptx', 'png', 'jpeg', 'jpg', 'bmp', 'tiff']
    filename_pattern = re.compile(
        rf"([^\s:]+\.(?:{'|'.join(allowed_extensions)})\s*:\s*.*?)(?=[^\s:]+\.(?:{'|'.join(allowed_extensions)})\s*:|$)",
        re.IGNORECASE | re.DOTALL
    )

    relevant_call_ids = set()
    data_points = []

    for msg in chat_log:
        if msg["message_type"] == "ToolCallRequestEvent":
            content = msg["content"][0]
            call_id_match = request_call_id_pattern.search(content)
            function_name_match = request_function_name_pattern.search(content)
            if call_id_match and function_name_match:
                if function_name_match.group(1) == "vector_index_retrieve_wrapper":
                    relevant_call_ids.add(call_id_match.group(1))
        elif msg["message_type"] == "ToolCallExecutionEvent":
            content = msg["content"][0]
            call_id_match = exec_call_id_pattern.search(content)
            if call_id_match and call_id_match.group(1) in relevant_call_ids:
                content_part_match = exec_content_pattern.search(content)
                if not content_part_match:
                    continue
                content_part = content_part_match.group(1)
                try:
                    parsed = json.loads(content_part)
                    texts = parsed.get("texts", [])
                except json.JSONDecodeError:
                    texts = [re.split(r'["\']images["\']\s*:\s*\[', content_part, 1, re.IGNORECASE)[0]]
                for text in texts:
                    text = bytes(text, "utf-8").decode("unicode_escape")
                    for match in filename_pattern.findall(text):
                        extracted = match.strip(" ,\\\"").lstrip("[").rstrip("],")
                        if extracted:
                            data_points.append(extracted)
    return DataPointsResult(data_points=data_points)
