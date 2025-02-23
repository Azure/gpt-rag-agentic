import requests
import json

def main():
    url = "http://localhost:7071/api/orcstream"  # Adjust URL as needed

    # Ask the user if they want text-only output
    text_only_input = input("Do you want text only output? (y/n): ").strip().lower()
    text_only = text_only_input == "y"
    
    payload = {
        "conversation_id": "",
        "question": "Write a detailed description of Microsoft Surface, at least 500 words.",
        "client_principal_id": "00000000-0000-0000-0000-000000000123",
        "client_principal_name": "anonymous",
        "text_only": text_only
    }
    headers = {"Content-Type": "application/json"}

    with requests.post(url, json=payload, headers=headers, stream=True) as response:
        response.raise_for_status()
        print("Streaming response:")
        for chunk in response.iter_content(chunk_size=128):
            if chunk:
                print(chunk.decode('utf-8'), end='', flush=True)
        print("\nDONE")

if __name__ == '__main__':
    main()
