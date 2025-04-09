import logging
import os
from connectors.blob import BlobContainerClient

def main(context: dict) -> list:
    """
    Activity function that connects to the storage container and returns a list of input blobs.
    The blobs are filtered to include only those from the 'input/' folder ending with '.jsonl'.
    """
    storage_account_name = os.getenv("AZURE_STORAGE_ACCOUNT")
    container_name = os.getenv("STORAGE_CONTAINER_BATCH")
    if not storage_account_name or not container_name:
        msg = "[batch_processing] AZURE_STORAGE_ACCOUNT and STORAGE_CONTAINER_BATCH environment variables must be set."
        logging.error(msg)
        raise Exception(msg)
    
    storage_account_url = f"https://{storage_account_name}.blob.core.windows.net"
    
    try:
        blob_container = BlobContainerClient(storage_account_url, container_name)
        logging.info(f"[batch_processing] Connected to container '{container_name}' at '{storage_account_url}'.")
        all_blobs = blob_container.list_blobs()
        input_blobs = [blob for blob in all_blobs if blob.startswith("input/") and blob.endswith(".jsonl")]
        logging.info(f"[batch_processing] Found {len(input_blobs)} input blob(s).")
        return input_blobs
    except Exception as e:
         msg = f"[batch_processing] Error listing input blobs: {str(e)}"
         logging.error(msg)
         raise Exception(msg)
