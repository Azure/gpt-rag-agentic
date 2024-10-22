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

# Apply the logging configuration without force=True
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)  # Use a module-specific logger

def load_environment():
    """
    Load environment variables from a `.env` file.

    Exits the program if required environment variables are missing.
    """
    load_dotenv()

    uri = os.getenv('ORCHESTRATOR_ENDPOINT')
    x_functions_key = os.getenv('FUNCTION_KEY')

    if not uri:
        print("Error: ORCHESTRATOR_ENDPOINT not found in environment variables.")
        sys.exit(1)
    if not x_functions_key:
        print("Error: FUNCTION_KEY not found in environment variables.")
        sys.exit(1)

    return uri, x_functions_key

def get_user_input():
    """
    Prompt the user to input a question.

    Returns:
        str: The user's input question.
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

def send_question(uri, x_functions_key, question, conversation_id):
    """
    Send the question to the ORC API and return the response.

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
            return response_data
        except json.JSONDecodeError:
            print("Error: Response is not valid JSON.")
            print(response.text)
            sys.exit(1)

    except requests.exceptions.RequestException as e:
        print(f"HTTP Request failed: {e}")
        sys.exit(1)

def display_answer(answer):
    """
    Display the assistant's answer, reasoning, and SQL query extracted from a JSON-formatted string or dictionary.

    Args:
        answer (str or dict): The assistant's answer in JSON format within a code block or as a dictionary.
                              Example as str:
                              ```json
                              {
                                "answer": "Your answer here.",
                                "reasoning": "Your reasoning here.",
                                "sql_query": "Your SQL query here."
                              }
                              ```
                              Example as dict:
                              {
                                "answer": "Your answer here.",
                                "reasoning": "Your reasoning here.",
                                "sql_query": "Your SQL query here."
                              }
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
        # If answer is a string, attempt to process it
        if isinstance(answer, str):
            # Remove the code block markers if present
            stripped_answer = answer.strip()
            if stripped_answer.startswith("```") and stripped_answer.endswith("```"):
                # Split the string into lines and exclude the first and last lines (the backticks)
                lines = stripped_answer.split("\n")
                # Check if the first line starts with ``` and possibly a language identifier like ```json
                if lines[0].startswith("```"):
                    lines = lines[1:-1]
                json_str = "\n".join(lines)
            else:
                json_str = stripped_answer

            # Parse the JSON content
            data = json.loads(json_str)

        elif isinstance(answer, dict):
            data = answer
        else:
            logger.error(f"Unsupported type for answer: {type(answer)}")
            print("Assistant: Unsupported answer format.")
            return

        # Ensure the parsed data is a dictionary
        if not isinstance(data, dict):
            logger.error("Parsed JSON is not a dictionary.")
            print("Assistant: The provided answer is not in the expected JSON object format.")
            return

        # Extract 'answer', 'reasoning', and 'sql_query' with default messages if keys are missing
        assistant_answer = data.get("answer")
        assistant_reasoning = data.get("reasoning")
        assistant_sql_query = data.get("sql_query")
        assistant_data_points = data.get("data_points")

        # Check if 'answer' key exists and is not empty
        if not assistant_answer:
            logger.warning("'answer' key is missing or empty in the provided data.")
            assistant_answer = "No answer provided."
        else:
            print(f"{BLUE}Answer: {assistant_answer}{RESET}")

        # Similarly check for 'reasoning'
        if not assistant_reasoning:
            logger.warning("'reasoning' key is missing or empty in the provided data.")
            assistant_reasoning = "No reasoning provided."
        else:
            print(f"{BLUE}Reasoning: {GREY}{assistant_reasoning}{RESET}")

        # Similarly check for 'sql_query'
        if not assistant_sql_query:
            logger.warning("'sql_query' key is missing or empty in the provided data.")
            assistant_sql_query = "No SQL query provided."
        else:
           print(f"{BLUE}SQL Query: {GREY}{assistant_sql_query}{RESET}")

        # Similarly check for 'data_points'
        if not assistant_data_points:
            logger.warning("'data_points' key is missing or empty in the provided data.")
            assistant_data_points = "No data_points provided."
        else:
            print(f"{BLUE}Data points: {GREY}{assistant_data_points}{RESET}")

    except json.JSONDecodeError as e:
        logger.error(f"JSON decoding failed: {e}")
        print("Assistant: Unable to parse the answer due to invalid JSON format.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        print("Assistant: An unexpected error occurred while processing the answer.")

def display_thoughts_and_data_points(response_data):
    """
    Display the thoughts and data_points from the API response.

    Args:
        response_data (dict): The API response as a JSON object.
    """
    thoughts = response_data.get('thoughts', '')
    data_points = response_data.get('data_points', '')
    if thoughts or data_points:
        
        BRIGHT_CYAN = '\033[96m'
        RESET = '\033[0m'

        print(f"{BRIGHT_CYAN}\n--- Agent Group Chat from Last Response ---")
        if thoughts:
            print(thoughts)
        if data_points:
            print("\nData Points:")
            print(data_points)
        print("---------------------------------------------------\n")
        print(f"{RESET}")
    else:
        logger.info("No group chat in the last response.")


def main():
    """
    Main function to execute the script logic.
    """
    uri, x_functions_key = load_environment()
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
            response_data = send_question(uri, x_functions_key, user_input, conversation_id)
            last_response_data = response_data
            # Update conversation_id
            if 'conversation_id' in response_data:
                conversation_id = response_data['conversation_id']
            # Display only the answer
            display_answer(response_data)

if __name__ == '__main__':
    main()
