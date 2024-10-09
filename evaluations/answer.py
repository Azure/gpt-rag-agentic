#!/usr/bin/env python3
"""
orc_client.py

A command-line client to send questions to the ORC API endpoint.

This script reads the API `URI` and `X_FUNCTIONS_KEY` from a `.env` file,
prompts the user to input a question, sends a POST request with the provided question,
and prints the response.

Usage:
    python answer.py

    Alternatively, after making the script executable:
    ./answer.py

Environment Variables:
    - ORCHESTRATOR_ENDPOINT: The API endpoint URI.
    - FUNCTION_KEY: The API access key.

Example `.env` File:
    ORCHESTRATOR_ENDPOINT=https://random-prefix.azurewebsites.net/api/orc
    FUNCTION_KEY=123ABCD==

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
        question = input("Please enter your question: ").strip()
        if not question:
            print("Error: Question cannot be empty.")
            sys.exit(1)
        return question
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)

def send_question(uri, x_functions_key, question):
    """
    Send the question to the ORC API and return the response.

    Args:
        uri (str): The API endpoint URI.
        x_functions_key (str): The API access key.
        question (str): The question to send.

    Returns:
        dict: The API response parsed as a JSON object.
    """
    headers = {
        'x-functions-key': x_functions_key,
        'Content-Type': 'application/json'
    }

    body = {
        'conversation_id': "",
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

def display_response(response_data):
    """
    Display the API response with proper Unicode characters.

    Args:
        response_data (dict): The API response as a JSON object.
    """
    try:
        # Pretty-print the JSON with Unicode characters unescaped
        pretty_json = json.dumps(response_data, indent=4, ensure_ascii=False)
        print(pretty_json)
    except TypeError as e:
        print("Error formatting the response:")
        print(e)
        print(response_data)

def main():
    """
    Main function to execute the script logic.
    """
    uri, x_functions_key = load_environment()
    question = get_user_input()
    response_data = send_question(uri, x_functions_key, question)
    display_response(response_data)

if __name__ == '__main__':
    main()
