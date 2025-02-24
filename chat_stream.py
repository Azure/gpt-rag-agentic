import requests
import logging
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_rest_api_config():
    """
    Load environment variables from a `.env` file.

    Exits the program if required environment variables are missing.

    Returns:
        tuple: Contains uri (str), x_functions_key (str)
    """
    load_dotenv()

    uri = os.getenv("STREAMING_ENDPOINT", "http://localhost:7071/api/orcstream")
    x_functions_key = os.getenv('FUNCTION_KEY')

    if not x_functions_key:
        print("FUNCTION_KEY not found in environment variables.")
        sys.exit(1)

    return uri, x_functions_key

def main():
    url, x_functions_key = get_rest_api_config()
    # Ask the user if they want text-only output
    text_only_input = input("Do you want text only output? (y/n): ").strip().lower()
    text_only = text_only_input != "n"
    
    payload = {
        "conversation_id": "",
        "question": "Write a detailed description of Microsoft Surface, at least 500 words.",
        "client_principal_id": "00000000-0000-0000-0000-000000000123",
        "client_principal_name": "anonymous",
        "text_only": text_only
    }
    headers = {
        'x-functions-key': x_functions_key,
        'Content-Type': 'application/json'
    }

    with requests.post(url, json=payload, headers=headers, stream=True) as response:
        response.raise_for_status()
        print("Streaming response:")
        for chunk in response.iter_content(chunk_size=128):
            if chunk:
                print(chunk.decode('utf-8'), end='', flush=True)
        print("\nDONE")

if __name__ == '__main__':
    main()
