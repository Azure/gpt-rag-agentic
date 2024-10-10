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

def display_answer(response_data):
    """
    Display the answer from the API response.

    Args:
        response_data (dict): The API response as a JSON object.
    """
    answer = response_data.get('answer', '')
    if answer:
        print(f"Assistant: {answer}")
    else:
        print("No answer provided in the response.")

def display_thoughts_and_data_points(response_data):
    """
    Display the thoughts and data_points from the API response.

    Args:
        response_data (dict): The API response as a JSON object.
    """
    thoughts = response_data.get('thoughts', '')
    data_points = response_data.get('data_points', '')
    if thoughts or data_points:
        print("\n--- Thoughts and Data Points from Last Response ---")
        if thoughts:
            print("Thoughts:")
            print(thoughts)
        if data_points:
            print("\nData Points:")
            print(data_points)
        print("---------------------------------------------------\n")
    else:
        print("No thoughts or data_points in the last response.")

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
