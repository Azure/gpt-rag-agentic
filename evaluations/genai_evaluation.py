#!/usr/bin/env python3
"""
evaluation.py

A script to evaluate questions either by sending them to a REST API or processing them locally
using the Orchestrator class. Additionally, results are saved to an Excel spreadsheet.

Usage:
    bash:
    export PYTHONPATH=./:$PYTHONPATH
    python evaluation.py --test-data path/to/test_data.jsonl

    Powershell:
    $env:PYTHONPATH = "./;$env:PYTHONPATH"    
    python evaluation.py --test-data path/to/test_data.jsonl

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
import logging
import logging.config
from dotenv import load_dotenv
import asyncio
import argparse
import pandas as pd  # Import pandas
import time

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

def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Evaluate questions either by sending them to a REST API or processing them locally."
    )
    parser.add_argument(
        "--test-data",
        type=str,
        required=True,
        help="Path to the test dataset file in JSONL format.",
    )
    return parser.parse_args()

def main():
    """
    Main function to execute the evaluation process.
    """
    args = parse_arguments()
    data_file_to_use = args.test_data

    # Check if the specified data file exists
    if not os.path.exists(data_file_to_use):
        logger.error(f"The specified data file '{data_file_to_use}' does not exist.")
        sys.exit(1)

    print(f"Using data file: {data_file_to_use}")

    load_dotenv()
    current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    use_rest_api = os.getenv('USE_REST_API', "False").lower() == "true"
    if use_rest_api:
        orchestrator_endpoint, function_key = get_rest_api_config()
        print("Configured to use REST API for processing questions.")
    else:
        orchestrator_endpoint = None
        function_key = None
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

    # Ensure 'evaluations' directory exists
    os.makedirs('evaluations', exist_ok=True)
    print("Ensured 'evaluations' directory exists.")

    output_jsonl_file = f"evaluations/responses_{current_time}.jsonl"
    output_excel_file = f"evaluations/responses_{current_time}.xlsx"  # Excel output file
    conversation_id = ""
    last_response_data = None

    # Initialize a list to collect all output data for Excel
    excel_data = []

    # Process each question in the test dataset
    with open(data_file_to_use, 'r', encoding='utf-8') as f_in, open(output_jsonl_file, 'w', encoding='utf-8') as f_out:
        print("Opened data file and output JSONL file.")
        for line_number, line in enumerate(f_in, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                question = data.get('question', '')
                ground_truth = data.get('ground_truth', '')
                print(f"Processing question {line_number}: {question}")

                start_time = time.time()
                # Process the question
                response_data = process_question(
                    question,
                    use_rest_api,
                    orchestrator_endpoint if use_rest_api else None,
                    function_key if use_rest_api else None,
                    conversation_id
                )
                duration = time.time() - start_time

                # Prepare the output data
                output_data = {
                    "Question": question,
                    "Ground Truth": ground_truth,
                    "Answer": response_data.get('answer', 'No answer provided.'),
                    "Context": response_data.get('data_points', 'No data points provided.'),
                    "Reasoning": response_data.get('reasoning', 'No reasoning provided.'),
                    "Processing Time (seconds)": duration
                }
                f_out.write(json.dumps(output_data) + '\n')

                # Append to excel_data list
                excel_data.append(output_data)

            except Exception as e:
                logger.exception(f"Error processing line {line_number}: {e}")

    print("Finished processing all questions.")
    # Optionally prettify the JSONL file
    prettify_jsonl_file(output_jsonl_file)

    # Save results to Excel
    try:
        df = pd.DataFrame(excel_data)
        df.to_excel(output_excel_file, index=False)
        print(f"Results have been saved to Excel file: '{output_excel_file}'")
    except Exception as e:
        logger.exception(f"Failed to save results to Excel: {e}")
        print(f"Error: Could not save results to Excel file. {e}")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.exception(f"An unhandled exception occurred: {e}")
        sys.exit(1)
