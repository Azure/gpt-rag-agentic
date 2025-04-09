import logging
import os
import json
import datetime
import asyncio
import re
from connectors.blob import BlobClient, BlobContainerClient
from orchestration import StreamingOrchestrator, OrchestratorConfig

def extract_conversation_id_from_chunk(chunk: str):
    """
    Extracts a UUID conversation ID from the beginning of a text chunk.
    """
    uuid_regex = re.compile(
        r'^\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\s+',
        re.IGNORECASE
    )
    match = uuid_regex.match(chunk)
    if match:
        conv_id = match.group(1)
        logging.info(f"[batch_processing] Extracted Conversation ID: {conv_id}")
        return conv_id, chunk[match.end():]
    return None, chunk

def main(blob_name: str) -> dict:
    """
    Activity function that processes a single input blob.
      - Downloads the blob content from the storage container.
      - Processes every line (each a JSON record) using StreamingOrchestrator.
      - Uploads the resulting output content to the 'output/' folder.
      - Returns details with the input and output blob names.
    """
    storage_account_name = os.getenv("AZURE_STORAGE_ACCOUNT")
    container_name = os.getenv("STORAGE_CONTAINER_BATCH")
    storage_account_url = f"https://{storage_account_name}.blob.core.windows.net"
    
    # Download blob content.
    try:
        blob_url = f"{storage_account_url}/{container_name}/{blob_name}"
        single_blob_client = BlobClient(blob_url)
        blob_bytes = single_blob_client.download_blob()
        content = blob_bytes.decode('utf-8')
        logging.info(f"[batch_processing] Downloaded blob: {blob_name}")
    except Exception as e:
        msg = f"[batch_processing] Error downloading blob {blob_name}: {e}"
        logging.error(msg)
        return {"input_blob": blob_name, "error": str(e)}
    
    output_lines = []
    last_conversation_id = ""
    line_number = 0

    # Process the file line by line.
    for line in content.splitlines():
        line_number += 1
        if not line.strip():
            continue
        
        try:
            record = json.loads(line)
        except Exception as e:
            logging.warning(f"[batch_processing] Skipping invalid JSON at line {line_number} in blob {blob_name}: {e}")
            continue
        
        followup = record.get("followup", "").strip().lower() if record.get("followup") else ""
        payload_conv = last_conversation_id if followup == "yes" else ""
        question = record.get("query", "")
        if not question:
            logging.warning(f"[batch_processing] No question found at line {line_number} in blob {blob_name}; skipping.")
            continue
        
        logging.info(f"[batch_processing] Processing blob {blob_name} line {line_number}: {question}")
        client_principal = {
            "id": record.get("client_principal_id", "00000000-0000-0000-0000-000000000000"),
            "name": record.get("client_principal_name", "anonymous"),
            "group_names": record.get("client_group_names", "")
        }
        access_token = record.get("access_token", None)
        conversation_id = payload_conv
        
        # Initialize the streaming orchestrator.
        orchestrator = StreamingOrchestrator(
            conversation_id, OrchestratorConfig(), client_principal, access_token
        )
        optimize_for_audio = record.get("optimize_for_audio", False)
        orchestrator.set_optimize_for_audio(optimize_for_audio)
        
        async def get_result():
            result_text = ""
            extracted_conv_id = None
            async for chunk in orchestrator.answer(question):
                if chunk:
                    if extracted_conv_id is None:
                        extracted_conv_id, chunk = extract_conversation_id_from_chunk(chunk)
                    result_text += chunk + "\n"
            return result_text, extracted_conv_id
        
        try:
            result_text, extracted_conv_id = asyncio.run(get_result())
        except Exception as e:
            logging.error(f"[batch_processing] Error processing question at line {line_number} in blob {blob_name}: {e}")
            result_text = f"Error processing question: {str(e)}"
            extracted_conv_id = None
        
        if extracted_conv_id:
            last_conversation_id = extracted_conv_id
            logging.info(f"[batch_processing] Updated conversation ID to: {extracted_conv_id}")
        
        record["response"] = result_text.strip()
        record["context"] = ""
        record["conversation_id"] = extracted_conv_id if extracted_conv_id else payload_conv
        output_lines.append(json.dumps(record))
    
    # Build the output blob name by replacing the "input/" folder with "output/" and appending a timestamp.
    base_input_name = blob_name.split("/")[-1]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_blob = f"output/{base_input_name.replace('.jsonl','')}_{timestamp}.jsonl"
    output_content = "\n".join(output_lines)
    
    try:
        # Upload output content from memory.
        blob_container = BlobContainerClient(storage_account_url, container_name)
        blob_client = blob_container.container_client.get_blob_client(output_blob)
        blob_client.upload_blob(output_content.encode("utf-8"), overwrite=True)
        logging.info(f"[batch_processing] Uploaded output blob: {output_blob}")
    except Exception as e:
        msg = f"[batch_processing] Error uploading output blob {output_blob}: {e}"
        logging.error(msg)
        return {"input_blob": blob_name, "error": str(e)}
    
    return {"input_blob": blob_name, "output_blob": output_blob}
