#!/usr/bin/env python3
"""
chat.py

A command-line client to interact with the ORC API endpoint in a continuous chat manner.

This script reads the API `URI` and `X_FUNCTIONS_KEY` from a `.env` file,
allows the user to have a continuous conversation with the orchestrator,
and handles special keyboard inputs to control the flow.

Usage:
    python chat.py

    Alternatively, after making the script executable:
    ./chat.py

Environment Variables:
    - ORCHESTRATOR_ENDPOINT: The API endpoint URI.
    - FUNCTION_KEY: The API access key.
    - CALL_ORCHESTRATOR_ENDPOINT: Set to "True" to use the remote orchestrator.

Requirements:
    - Python 3.x
    - requests library (`pip install requests`)
    - python-dotenv library (`pip install python-dotenv`)

Security Note:
    Ensure that your `.env` file is not committed to version control systems
    as it contains sensitive information. Add `.env` to your `.gitignore` file.
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv
import logging
import logging.config
from orchestration import Orchestrator
import asyncio
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

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
            'filename': 'output.log',
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
    'loggers': {
        # Explicitly configure external loggers to propagate to root
        'shared.util': {
            'handlers': ['file_handler'],  # Only file handler
            'level': 'INFO',
            'propagate': True,
        },
        # Add more external loggers here if needed
    },
}

# Apply the logging configuration
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)  # Use a module-specific logger


def get_rest_api_config():
    """
    Load environment variables from a `.env` file.

    Exits the program if required environment variables are missing.

    Returns:
        tuple: Contains uri (str), x_functions_key (str)
    """
    load_dotenv()

    uri = os.getenv('ORCHESTRATOR_ENDPOINT')
    x_functions_key = os.getenv('FUNCTION_KEY')

    if not uri:
        logger.error("ORCHESTRATOR_ENDPOINT not found in environment variables.")
        sys.exit(1)
    if not x_functions_key:
        logger.error("FUNCTION_KEY not found in environment variables.")
        sys.exit(1)

    return uri, x_functions_key

def get_user_input():
    """
    Prompt the user to input a question.

    Returns:
        str: The user's input question, or special commands like 'CTRL_D'.
    """
    try:
        question = input("You: ").strip()
        if not question:
            print("Error: Input cannot be empty.")
            return None
        return question
    except EOFError:
        # Ctrl+D pressed
        return 'CTRL_D'
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)


def send_question_to_python(question, conversation_id):
    """
    Process the question using the orchestrator.

    Args:
        question (str): The user's question.
        conversation_id (str): The conversation ID.

    Returns:
        dict: The response from the orchestrator.
    """
    # Use default client principal information
    client_principal = {
        'id': '00000000-0000-0000-0000-000000000123',
        'name': 'anonymous',
        'group_names': ''        
    }


    # Call orchestrator
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


def display_answer(answer):
    """
    Display the assistant's answer, reasoning, and SQL query extracted from a JSON-formatted string or dictionary.

    Args:
        answer (dict): The assistant's answer in dictionary format.
    """
    if not answer:
        logger.warning("No answer provided.")
        print("No answer provided.")
        return

    # ANSI escape sequences for colors
    BLUE = '\033[94m'
    GREY = '\033[90m'
    RESET = '\033[0m'

    try:
        # Ensure the answer is a dictionary
        if isinstance(answer, str):
            answer = json.loads(answer)

        if not isinstance(answer, dict):
            logger.error("Parsed JSON is not a dictionary.")
            print("Assistant: The provided answer is not in the expected JSON object format.")
            return

        # Extract keys with default messages if keys are missing
        assistant_answer = answer.get("answer", "No answer provided.")
        assistant_reasoning = answer.get("reasoning", "No reasoning provided.")
        assistant_data_points = answer.get("data_points", "No data points provided.")

        print(f"{BLUE}Answer: {assistant_answer}{RESET}")
        print(f"{BLUE}Reasoning: {GREY}{assistant_reasoning}{RESET}")
        print(f"{BLUE}Data Points: {GREY}{assistant_data_points}{RESET}")

    except json.JSONDecodeError as e:
        logger.error(f"JSON decoding failed: {e}")
        print("Assistant: Unable to parse the answer due to invalid JSON format.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
        print("Assistant: An unexpected error occurred while processing the answer.")


def display_thoughts_and_data_points(response_data):
    """
    Display the thoughts and data_points from the API response.

    Args:
        response_data (dict): The API response as a JSON object.
    """
    thoughts = response_data.get('thoughts', '')
    reasoning = response_data.get('reasoning', '')    
    data_points = response_data.get('data_points', '')
    if thoughts or data_points or reasoning:
        BRIGHT_CYAN = '\033[96m'
        RESET = '\033[0m'

        print(f"{BRIGHT_CYAN}\n--- Agent Group Chat from Last Response ---")
        if data_points:
            print("\nReasoning:")
            print(reasoning)
        if thoughts:
            print("\nThoughts:")            
            print(thoughts)
        if data_points:
            print("\nData Points:")
            print(data_points)
        print("---------------------------------------------------\n")
        print(f"{RESET}")
    else:
        logger.info("No thoughts or data points in the last response.")


def main():
    """
    Main function to execute the script logic.
    """
    conversation_id = ""
    last_response_data = None

    while True:
        user_input = get_user_input()
        if user_input == 'CTRL_D':
            # Display thoughts and data_points from last_response_data
            if last_response_data:
                display_thoughts_and_data_points(last_response_data)
            else:
                print("No previous response to display thoughts and data points.")
            continue
        elif user_input is None:
            continue
        else:
            use_rest_api = os.getenv('USE_REST_API', "False").lower() == "true"
            if use_rest_api:
                uri, x_functions_key = get_rest_api_config()
                response_data = send_question_to_rest_api(
                    uri, x_functions_key, user_input, conversation_id)
            else:
                response_data = send_question_to_python(user_input, conversation_id)

            if 'error' in response_data:
                print(f"Error: {response_data['error']}")
                logger.error(f"Error in response: {response_data['error']}")
                continue

            last_response_data = response_data
            # Update conversation_id
            if 'conversation_id' in response_data:
                conversation_id = response_data['conversation_id']
            else:
                logger.warning("No conversation_id in response data.")

            # Display only the answer
            display_answer(response_data)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.exception(f"An unhandled exception occurred: {e}")
        sys.exit(1)
