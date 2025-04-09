#!/usr/bin/env python3
import os
import sys
import json
import requests
import argparse
import datetime
import re
import logging
from dotenv import load_dotenv
load_dotenv()

"""
Evaluation Script Using REST API with Streaming Response

This script reads input questions from a `.jsonl` file, sends them to a REST API endpoint,
and writes the results to a new `.jsonl` file with additional metadata.

The API is expected to support a streaming response with the option to include a UUID
conversation ID in the first chunk of the response.

Environment Variables:
----------------------
- ORCHESTRATOR_ENDPOINT : str
    The URL of the REST API endpoint.
- FUNCTION_KEY : str
    The access key required to authenticate with the API.

Command-line Arguments:
-----------------------
--input : str
    Path to the input .jsonl file. Default is 'evaluations/input/test-dataset.jsonl'.
--output-folder : str
    Directory where the output .jsonl file will be saved. Default is 'evaluations/output/'.

Input File Format (.jsonl):
---------------------------
Each line must be a JSON object with the following fields:

- query (str): The question to be sent to the REST API.
- ground_truth (str, optional): Expected answer, used for evaluation or reference.
- conversation (str, optional): Existing conversation ID for continued dialogue.

Example:
    {
        "query": "What is Zero Trust?",
        "ground_truth": "Zero Trust is a security model...",
        "conversation": ""
    }

Output File Format (.jsonl):
----------------------------
Each output line is a JSON object with the same fields from the input, plus:

- response (str): The text response returned by the REST API.
- context (str): Placeholder for future context, currently empty.
- conversation_id (str): UUID extracted from the response or reused from the input.

Example:
    {
        "query": "What is Zero Trust?",
        "ground_truth": "Zero Trust is a security model...",
        "conversation": "",
        "response": "Zero Trust is a framework that assumes...",
        "context": "",
        "conversation_id": "123e4567-e89b-12d3-a456-426614174000"
    }

Functions:
----------
- extract_conversation_id_from_chunk(chunk: str) -> tuple[str | None, str]:
    Extracts a UUID conversation ID from the start of a text chunk, if present.

- send_question_to_rest_api(uri: str, function_key: str, question: str, conversation_id: str) -> tuple[str | None, str]:
    Sends a question to the API and returns the streaming response along with any extracted conversation ID.

Usage:
------
    python3 script.py --input path/to/input.jsonl --output-folder path/to/output/

This script can be used for testing, evaluation, and orchestration flows that rely on text generation via APIs.

"""

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

"""
Evaluation Script Using REST API with Streaming Response

This script reads input questions from a `.jsonl` file, sends them to a REST API endpoint,
and writes the results to a new `.jsonl` file with additional metadata.
"""

UUID_REGEX = re.compile(
    r'^\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\s+',
    re.IGNORECASE
)

def extract_conversation_id_from_chunk(chunk: str):
    """
    Extracts a UUID conversation ID from the beginning of a text chunk.
    """
    match = UUID_REGEX.match(chunk)
    if match:
        conv_id = match.group(1)
        logging.info("Extracted Conversation ID: %s", conv_id)
        return conv_id, chunk[match.end():]
    return None, chunk

def send_question_to_rest_api(uri, function_key, question, conversation_id):
    """
    Sends the question to the REST API endpoint and returns its streaming text response.
    """
    headers = {
        "x-functions-key": function_key,
        "Content-Type": "application/json"
    }
    payload = {
        "conversation_id": conversation_id,
        "query" : question
    }
    try:
        logging.debug("Sending POST request to API with conversation ID: %s", conversation_id)
        response = requests.post(uri, headers=headers, json=payload, stream=True)
        response.raise_for_status()

        result_text = ""
        extracted_conv_id = None
        for chunk in response.iter_lines(decode_unicode=True):
            if chunk:
                if extracted_conv_id is None:
                    extracted_conv_id, chunk = extract_conversation_id_from_chunk(chunk)
                result_text += chunk + "\n"
        logging.debug("Received response from API.")
        return extracted_conv_id, result_text.strip()
    except Exception as e:
        logging.error("Error while calling REST API: %s", e)
        return None, f"Error: {str(e)}"

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
        logging.error("Input file '%s' not found.", input_file)
        sys.exit(1)

    os.makedirs(output_folder, exist_ok=True)

    endpoint = os.getenv("ORCHESTRATOR_STREAM_ENDPOINT")
    function_key = os.getenv("FUNCTION_KEY")

    if not endpoint or not function_key:
        logging.error("Environment variables ORCHESTRATOR_STREAM_ENDPOINT and FUNCTION_KEY must be set.")
        sys.exit(1)

    base_name = os.path.basename(input_file)
    name, ext = os.path.splitext(base_name)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_folder, f"{name}_{timestamp}{ext}")

    logging.info("Starting evaluation script.")
    logging.info("Input file: %s", input_file)
    logging.info("Output file: %s", output_file)
    logging.info("API endpoint: %s", endpoint)

    last_conversation_id = ""
    line_number = 0

    with open(input_file, "r", encoding="utf-8") as fin, \
         open(output_file, "w", encoding="utf-8") as fout:
        for line in fin:
            line_number += 1
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except Exception as e:
                logging.warning("Skipping invalid JSON on line %d: %s", line_number, e)
                continue

            followup = record.get("followup", "").strip().lower()
            payload_conv = last_conversation_id if followup == "yes" else ""

            question = record.get("query", record.get("query" , ""))
            if not question:
                logging.warning("No question found in line %d; skipping.", line_number)
                continue

            logging.info("Sending question on line %d: %s", line_number, question)
            extracted_conv_id, response_text = send_question_to_rest_api(
                endpoint, function_key, question, payload_conv
            )

            if extracted_conv_id:
                last_conversation_id = extracted_conv_id
                logging.info("Conversation ID updated to: %s", extracted_conv_id)

            record["response"] = response_text
            record["context"] = ""
            record["conversation_id"] = extracted_conv_id if extracted_conv_id else payload_conv

            fout.write(json.dumps(record) + "\n")
            logging.info("Response written for line %d", line_number)

    logging.info("Processing complete. Output written to: %s", output_file)

if __name__ == "__main__":
    main()
