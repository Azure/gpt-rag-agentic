#!/usr/bin/env python3
"""
evaluation.py

A script to evaluate questions either by sending them to a REST API or processing them locally
using the Orchestrator class.

Usage:
    bash:
    export PYTHONPATH=./:$PYTHONPATH
    python evaluation.py

    Powershell:
    $env:PYTHONPATH = "./;$env:PYTHONPATH"    
    python evaluation.py

    Environment Variables:
    - USE_REST_API: Set to "True" to use the REST API for processing questions. Otherwise, local execution is used.
    - ORCHESTRATOR_ENDPOINT: The API endpoint URI (required if USE_REST_API is "True").
    - FUNCTION_KEY: The API access key (required if USE_REST_API is "True").
    - AZURE_OPENAI_ENDPOINT: Azure OpenAI endpoint.
    - AZURE_OPENAI_API_VERSION: Azure OpenAI API version.
    - AZURE_OPENAI_API_KEY: Azure OpenAI API key.
    - AZURE_SUBSCRIPTION_ID: Azure subscription ID.
    - AZURE_RESOURCE_GROUP: Azure resource group.
    - AZUREAI_PROJECT_NAME: Azure AI project name.

Requirements:
    - Python 3.x
    - requests library (`pip install requests`)
    - python-dotenv library (`pip install python-dotenv`)
    - promptflow library (`pip install promptflow`)
    - pandas library (`pip install pandas`)
    - openpyxl library (`pip install openpyxl`)

Security Note:
    Ensure that your `.env` file is not committed to version control systems
    as it contains sensitive information. Add `.env` to your `.gitignore` file.
"""

import os
import sys
import json
import requests
import datetime
import time
import logging
import logging.config
from dotenv import load_dotenv
import pandas as pd
from promptflow.client import PFClient
import asyncio

# Import Orchestrator for local execution
try:
    from orchestration import Orchestrator
except ImportError:
    print("Error: Could not import Orchestrator from 'orchestration' module.")
    sys.exit(1)

# Configure logging
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,  # Allow existing loggers to propagate
    'formatters': {
        'standard': {
            'format': '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        },
    },
    'handlers': {
        'file_handler': {
            'class': 'logging.FileHandler',
            'filename': 'evaluation.log',
            'mode': 'a',
            'formatter': 'standard',
            'level': 'INFO',
        },
        'console_handler': {
            'class': 'logging.StreamHandler',
            'stream': sys.stdout,
            'formatter': 'standard',
            'level': 'ERROR',
        },
    },
    'root': {
        'handlers': ['file_handler', 'console_handler'],
        'level': 'DEBUG',
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)  # Use a module-specific logger

def get_rest_api_config():
    """
    Load environment variables required for REST API configuration.

    Returns:
        tuple: (orchestrator_endpoint, function_key)
    """
    orchestrator_endpoint = os.getenv('ORCHESTRATOR_ENDPOINT')
    function_key = os.getenv('FUNCTION_KEY')

    if not orchestrator_endpoint:
        logger.error("ORCHESTRATOR_ENDPOINT not found in environment variables.")
        sys.exit(1)
    if not function_key:
        logger.error("FUNCTION_KEY not found in environment variables.")
        sys.exit(1)

    return orchestrator_endpoint, function_key

def send_question_to_rest_api(uri, x_functions_key, question, conversation_id):
    """
    Send the question to the orchestrator API and return the response.

    Args:
        uri (str): The API endpoint URI.
        x_functions_key (str): The API access key.
        question (str): The question to send.
        conversation_id (str): The conversation ID.

    Returns:
        dict: The API response parsed as a JSON object.
    """
    headers = {
        'x-functions-key': x_functions_key,
        'Content-Type': 'application/json'
    }

    body = {
        'conversation_id': conversation_id,
        'question': question
    }

    try:
        response = requests.post(uri, headers=headers, json=body)
        response.raise_for_status()  # Raises HTTPError for bad responses

        try:
            response_data = response.json()
            if not isinstance(response_data, dict):
                logger.error("Response JSON is not a dictionary.")
                return {"error": "Invalid response format from orchestrator API."}
            return response_data
        except json.JSONDecodeError:
            logger.error("Response is not valid JSON.")
            return {"error": "Response is not valid JSON."}

    except requests.exceptions.RequestException as e:
        logger.exception(f"HTTP Request failed: {e}")
        return {"error": f"HTTP Request failed: {e}"}

def send_question_to_python(question, conversation_id):
    """
    Process the question using the Orchestrator locally.

    Args:
        question (str): The user's question.
        conversation_id (str): The conversation ID.

    Returns:
        dict: The response from the Orchestrator.
    """
    client_principal = {
        'id': '00000000-0000-0000-0000-000000000000',
        'name': 'anonymous'
    }

    if question:
        try:
            orchestrator = Orchestrator(conversation_id, client_principal)
            result = asyncio.run(orchestrator.answer(question))
            if not isinstance(result, dict):
                logger.error("Expected result to be a dictionary.")
                return {"error": "Invalid response format from orchestrator."}
            return result
        except Exception as e:
            logger.exception(f"An error occurred while orchestrating the question: {e}")
            return {"error": "An error occurred while processing your question."}
    else:
        logger.warning("No question provided to orchestrate.")
        return {"error": "No question provided."}

def process_question(question, use_rest_api, orchestrator_endpoint, function_key, conversation_id):
    """
    Process a single question either via REST API or locally.

    Args:
        question (str): The question to process.
        use_rest_api (bool): Flag to determine the method of processing.
        orchestrator_endpoint (str): The API endpoint URI.
        function_key (str): The API access key.
        conversation_id (str): The conversation ID.

    Returns:
        dict: The response from the chosen processing method.
    """
    if use_rest_api:
        response_data = send_question_to_rest_api(
            orchestrator_endpoint, function_key, question, conversation_id)
    else:
        response_data = send_question_to_python(question, conversation_id)
    
    return response_data

import os
import json

def prettify_jsonl_file(input_file):
    # Check if the input file exists
    if not os.path.isfile(input_file):
        print(f"Error: The file '{input_file}' does not exist.")
        return

    try:
        # Read the entire content from the input file first
        with open(input_file, 'r', encoding='utf-8') as infile:
            lines = infile.readlines()

        # Prettify the content and write back to the same file
        with open(input_file, 'w', encoding='utf-8') as outfile:
            for line in lines:
                # Load the JSON object from the line
                json_obj = json.loads(line.strip())
                # Write the pretty-printed JSON back to the file
                json.dump(json_obj, outfile, indent=4, ensure_ascii=False)
                outfile.write('\n')  # Add a newline after each JSON object

        print(f"Prettified JSONL content has been written to '{input_file}'")
    except Exception as e:
        print(f"Error occurred while processing the file: {e}")


def main():
    """
    Main function to execute the evaluation process.
    """
    print("Starting evaluation process...")
    load_dotenv()
    current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    use_rest_api = os.getenv('USE_REST_API', "False").lower() == "true"
    if use_rest_api:
        orchestrator_endpoint, function_key = get_rest_api_config()
        print("Configured to use REST API for processing questions.")
    else:
        print("Configured to use local execution for processing questions.")

    # Azure configuration (used if needed)
    azure_config = {
        "aoai_endpoint": os.environ.get('AZURE_OPENAI_ENDPOINT', ''),
        "aoai_api_version": os.environ.get('AZURE_OPENAI_API_VERSION', '2024-02-01'),
        "aoai_api_key": os.environ.get('AZURE_OPENAI_API_KEY', ''),
        "subscription_id": os.environ.get('AZURE_SUBSCRIPTION_ID', ''),
        "resource_group": os.environ.get('AZURE_RESOURCE_GROUP', ''),
        "project_name": os.environ.get('AZUREAI_PROJECT_NAME', '')
    }
    print("Azure configuration loaded.")

    ##################################
    ## Base Run
    ##################################

    data_file = "evaluations/test-dataset.jsonl"
    custom_data_file = "evaluations/test-dataset.custom.jsonl"
    output_file = f"evaluations/responses_{current_time}.jsonl"
    print("File paths set.")

    # Ensure 'evaluations' directory exists
    os.makedirs('evaluations', exist_ok=True)
    print("Ensured 'evaluations' directory exists.")

    # Determine which data file to use
    if os.path.exists(custom_data_file):
        data_file_to_use = custom_data_file
        print(f"Using custom data file: {custom_data_file}")
    elif os.path.exists(data_file):
        data_file_to_use = data_file
        print(f"Using default data file: {data_file}")
    else:
        logger.error("Neither custom_data_file nor data_file exists.")
        raise FileNotFoundError("Neither custom_data_file nor data_file exists.")
    print(f"Data file to use: {data_file_to_use}")

    conversation_id = ""
    last_response_data = None

    # Process each question in the test dataset
    with open(data_file_to_use, 'r', encoding='utf-8') as f_in, open(output_file, 'w', encoding='utf-8') as f_out:
        print("Opened data file and output file.")
        for line_number, line in enumerate(f_in, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                # Attempt to parse the JSON line
                data = json.loads(line)
                question = data.get('question', '')
                ground_truth = data.get('ground_truth', '')
                print(f"Processing question {line_number}: {question}")

                # Prepare the request payload
                request_body = {
                    "conversation_id": conversation_id,
                    "question": question
                }
                
                # Start timing
                start_time = time.time()

                # Process the question
                response_data = process_question(
                    question,
                    use_rest_api,
                    orchestrator_endpoint if use_rest_api else None,
                    function_key if use_rest_api else None,
                    conversation_id
                )

                # End timing
                end_time = time.time()
                duration = end_time - start_time

                if 'error' in response_data:
                    error_message = response_data['error']
                    print(f"Error: {error_message} for question: {question}")
                    logger.error(f"Error processing question '{question}': {error_message}")
                    answer = error_message
                    data_points = ""
                    thoughts = ""
                else:
                    answer = response_data.get('answer', 'No answer provided.')
                    data_points = response_data.get('data_points', 'No data points provided.')
                    thoughts = response_data.get('thoughts', 'No thoughts provided.')
                    reasoning = response_data.get('reasoning', 'No reasoning provided.')
                    sql_query = response_data.get('sql_query', 'No SQL query provided.')

                    # Update conversation_id if present
                    conversation_id = response_data.get('conversation_id', conversation_id)

                print(f"Processing time for question '{question}': {duration:.2f} seconds")

            except json.JSONDecodeError as e:
                error_message = f"JSON decoding failed: {e}"
                print(f"{error_message} for line {line_number}")
                logger.error(f"{error_message} for line {line_number}")
                answer = error_message
                data_points = ""
                thoughts = ""
                duration = 0  # Set duration to zero if there's an error
            except Exception as e:
                error_message = f"Unexpected error: {e}"
                print(f"{error_message} for question: {question}")
                logger.exception(f"{error_message} for question: {question}")
                answer = error_message
                data_points = ""
                thoughts = ""
                duration = 0  # Set duration to zero if there's an error

            # Prepare and write the output JSON
            output_data = {
                "question": question,
                "ground_truth": ground_truth,
                "answer": answer,
                "context": data_points,
                "thoughts": thoughts,
                "reasoning": reasoning,
                "sql_query": sql_query,                
                "processing_time_seconds": f"{duration:.2f}"  # Include processing time
            }
            f_out.write(json.dumps(output_data) + '\n')

    print("Finished processing all questions.")

    ##################################
    ## Evaluation Run
    ##################################

    try:
        pf = PFClient()
    except Exception as e:
        logger.exception(f"Failed to initialize PFClient: {e}")
        print("Failed to initialize PromptFlow client.")
        sys.exit(1)

    eval_prompty = "evaluations/genai-score-eval.prompty"
    print("Starting evaluation run...")
    try:
        eval_run = pf.run(
            flow=eval_prompty,
            data=output_file,  
            column_mapping={
                "question": "${data.question}",
                "answer": "${data.answer}",
                "ground_truth": "${data.ground_truth}",
                "context": "${data.context}",
                "reasoning":  "${data.reasoning}",
                "sql_query":  "${data.sql_query}",
                "group_chat":  "${data.thoughts}"
            },
            stream=True,
        )
        print("Evaluation run completed.")
    except Exception as e:
        logger.exception(f"Failed during evaluation run: {e}")
        print("Failed during evaluation run.")
        sys.exit(1)

    try:
        details = pf.get_details(eval_run)
        print("Retrieved evaluation details.")
    except Exception as e:
        logger.exception(f"Failed to retrieve evaluation details: {e}")
        print("Failed to retrieve evaluation details.")
        sys.exit(1)

    try:
        # Compute the averages of outputs.similarity_score and outputs.groundedness_score
        average_score = details['outputs.similarity_score'].mean()
        average_groundedness_score = details['outputs.groundedness_score'].mean()

        # Create a new row with averages
        average_row = {}
        for col in details.columns:
            if col == 'inputs.question':
                average_row[col] = 'Average'
            elif col == 'outputs.similarity_score':
                average_row[col] = average_score
            elif col == 'outputs.groundedness_score':
                average_row[col] = average_groundedness_score
            else:
                average_row[col] = ''

        # Append the new row to the DataFrame
        average_df = pd.DataFrame([average_row])
        details = pd.concat([details, average_df], ignore_index=True)

        # Save output to an Excel file 
        filename = f"evaluations/genai-score-eval_{current_time}.xlsx"
        details.to_excel(filename, index=False)
        print(f"Saved evaluation details to Excel file: {filename}")
    except Exception as e:
        logger.exception(f"Failed to process evaluation details: {e}")
        print("Failed to process evaluation details.")
        sys.exit(1)

    # Prettify the JSONL file by formatting it with proper indentation and overwriting the original file
    prettify_jsonl_file(output_file)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.exception(f"An unhandled exception occurred: {e}")
        sys.exit(1)
