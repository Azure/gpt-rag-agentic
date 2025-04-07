#!/usr/bin/env python3
import os
import sys
import json
import requests
import argparse
import datetime
import re
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)

# Regex to extract a UUID at the start of a chunk.
UUID_REGEX = re.compile(
    r'^\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\s+',
    re.IGNORECASE
)

def extract_conversation_id_from_chunk(chunk: str):
    """
    Extracts a UUID conversation ID from the beginning of a text chunk.
    
    Args:
        chunk (str): The text chunk from the orchestrator response.
        
    Returns:
        tuple: (conversation_id (str or None), cleaned_chunk (str))
    """
    match = UUID_REGEX.match(chunk)
    if match:
        conv_id = match.group(1)
        logging.info("Extracted Conversation ID: %s", conv_id)
        return conv_id, chunk[match.end():]
    return None, chunk

def send_question_to_rest_api(uri, function_key, question, conversation_id):
    """
    Sends the question to the REST API endpoint and returns its streaming text response,
    while extracting the conversation ID from the first chunk.
    
    Args:
        uri (str): The API endpoint URL.
        function_key (str): The API access key.
        question (str): The question to process.
        conversation_id (str): The conversation identifier to send (may be empty).
    
    Returns:
        tuple: (extracted_conversation_id (str or None), complete text response (str))
    """
    headers = {
        "x-functions-key": function_key,
        "Content-Type": "application/json"
    }
    payload = {
        "conversation_id": conversation_id,
        "question": question
    }
    try:
        response = requests.post(uri, headers=headers, json=payload, stream=True)
        response.raise_for_status()
        result_text = ""
        extracted_conv_id = None
        for chunk in response.iter_lines(decode_unicode=True):
            if chunk:
                # Try to extract the conversation ID from the first non-empty chunk.
                if extracted_conv_id is None:
                    extracted_conv_id, chunk = extract_conversation_id_from_chunk(chunk)
                result_text += chunk + "\n"
        return extracted_conv_id, result_text.strip()
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        return None, error_msg

def main():
    parser = argparse.ArgumentParser(
        description="Simple evaluation script using a streaming REST API."
    )
    parser.add_argument(
        "--input", type=str, default="evaluations/input/test-dataset.jsonl",
        help="Path to the input JSONL file."
    )
    parser.add_argument(
        "--output-folder", type=str, default="evaluations/output/",
        help="Directory where the output JSONL file will be saved."
    )
    args = parser.parse_args()

    input_file = args.input
    output_folder = args.output_folder

    if not os.path.exists(input_file):
        print(f"Input file '{input_file}' not found.")
        sys.exit(1)

    os.makedirs(output_folder, exist_ok=True)

    # Use the correct environment variable name for the streaming endpoint.
    endpoint = os.getenv("ORCHESTRATOR_STREAM_ENDPOINT")
    function_key = os.getenv("FUNCTION_KEY")
    if not endpoint or not function_key:
        print("Environment variables ORCHESTRATOR_STREAM_ENDPOINT and FUNCTION_KEY must be set.")
        sys.exit(1)

    base_name = os.path.basename(input_file)
    name, ext = os.path.splitext(base_name)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_folder, f"{name}_{timestamp}{ext}")

    # Variable to store the conversation ID from the previous response.
    last_conversation_id = ""
    with open(input_file, "r", encoding="utf-8") as fin, \
         open(output_file, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except Exception as e:
                print(f"Skipping invalid JSON line: {line}")
                continue

            # Check if the record indicates a followup.
            followup = record.get("followup", "").strip().lower()
            if followup == "yes":
                payload_conv = last_conversation_id
            else:
                payload_conv = ""

            question = record.get("query", record.get("question", ""))
            ground_truth = record.get("ground_truth", "")

            # Call the REST API with the appropriate conversation ID.
            extracted_conv_id, response_text = send_question_to_rest_api(
                endpoint, function_key, question, payload_conv
            )

            # Update last_conversation_id if a new one was extracted.
            if extracted_conv_id:
                last_conversation_id = extracted_conv_id

            record["response"] = response_text
            record["context"] = ""
            record["conversation_id"] = extracted_conv_id if extracted_conv_id else payload_conv

            fout.write(json.dumps(record) + "\n")

    print(f"Output written to: {output_file}")

if __name__ == "__main__":
    main()
