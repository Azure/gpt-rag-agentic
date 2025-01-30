from typing_extensions import Annotated
from connectors import AzureOpenAIClient
from azure.identity import ManagedIdentityCredential, AzureCliCredential, ChainedTokenCredential
import os
import time
import logging
import requests
import json  # Import json for structured output

import os
import json
import time
import logging
import requests
from azure.identity import ChainedTokenCredential, ManagedIdentityCredential, AzureCliCredential
from typing import Annotated

def queries_retrieval(
    input: Annotated[str, "An optimized query string based on the user's ask and conversation history, when available"],
    datasource: Annotated[str, "Datasource name"] = None,
) -> Annotated[str, "The output is a JSON string with the search results containing question, query, selected_tables, selected_columns, and reasoning"]:
    aoai = AzureOpenAIClient()

    VECTOR_SEARCH_APPROACH = 'vector'
    TERM_SEARCH_APPROACH = 'term'
    HYBRID_SEARCH_APPROACH = 'hybrid'

    # Customize the search parameters
    search_index = os.getenv('AZURE_SEARCH_INDEX', 'queries')	
    search_approach = os.getenv('AZURE_SEARCH_APPROACH', HYBRID_SEARCH_APPROACH)
    search_top_k = 3
    # Semantic
    use_semantic = os.getenv('AZURE_SEARCH_USE_SEMANTIC', "false").lower() == "true"
    semantic_search_config = os.getenv('AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG', 'my-semantic-config')
    search_service = os.getenv('AZURE_SEARCH_SERVICE')
    search_api_version = os.getenv('AZURE_SEARCH_API_VERSION', '2024-07-01')

    search_results = []
    search_query = input
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
        # Prepare body with the desired fields
        body = {
            "select": "question, query, selected_tables, selected_columns, reasoning",
            "top": search_top_k
        }
        
        # Add filter for datasource if provided
        if datasource:
            # Ensure proper escaping of quotes if datasource contains them
            safe_datasource = datasource.replace("'", "''")
            body["filter"] = f"datasource eq '{safe_datasource}'"

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
        json_response = response.json()
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
                    question = doc.get('question', '')
                    query = doc.get('query', '')
                    selected_tables = doc.get('selected_tables', [])
                    selected_columns = doc.get('selected_columns', [])
                    reasoning = doc.get('reasoning', '')

                    # Append the extracted information as a dictionary
                    search_results.append({
                        "question": question,
                        "query": query,
                        "selected_tables": selected_tables,
                        "selected_columns": selected_columns,
                        "reasoning": reasoning
                    })
            else:
                logging.info(f"[ai_search] No documents retrieved")

        response_time = round(time.time() - start_time, 2)
        logging.info(f"[ai_search] Finished querying Azure AI Search. {response_time} seconds")

    except Exception as e:
        error_message = str(e)
        logging.error(f"[ai_search] Error when getting the answer: {error_message}")

    # Convert the search_results list of dictionaries to a JSON string
    return json.dumps(search_results, indent=2)