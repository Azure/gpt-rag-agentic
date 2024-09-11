import logging
import os
import time
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential

MAX_RETRIES = 10  # Maximum number of retries for rate limit errors

class CosmosDBClient:
    """
    CosmosDBClient uses the Cosmos SDK's retry mechanism with exponential backoff.
    The number of retries is controlled by the MAX_RETRIES environment variable.
    Delays between retries start at 0.5 seconds, doubling up to 8 seconds.
    If a rate limit error occurs after retries, the client will retry once more after the retry-after-ms header duration (if the header is present).
    """

    def __init__(self):
        """
        Initializes the Cosmos DB client with credentials and endpoint.
        """
        # Get Azure Cosmos DB configuration
        self.db_id = os.environ.get("AZURE_DB_ID")
        self.db_name = os.environ.get("AZURE_DB_NAME")
        self.db_uri = f"https://{self.db_id}.documents.azure.com:443/"

# 'conversations'
# self.conversation_id
#     conversation
#     logging.info(f"[base_orchestrator] customer sent an inexistent conversation_id, saving new conversation_id")        
#     conversation = await container.create_item(body={"id": self.conversation_id})
# self.conversation_data = self.conversation.get('conversation_data', 
#                             {'start_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'interactions': []})
# self.history = self.conversation_data.get('history', [])

    async def get_document(self, container, key) -> dict: 
        async with DefaultAzureCredential() as credential:    
            async with CosmosClient(self.db_uri, credential=credential) as db_client:
                db = db_client.get_database_client(database=self.db_name)
                container = db.get_container_client(container)
                try:
                    document = await container.read_item(item=key, partition_key=key)
                    logging.info(f"[cosmosdb] document {key} retrieved.")
                except Exception as e:
                    document = None
                    logging.info(f"[cosmosdb] document {key} does not exist.")
                return document

    async def create_document(self, container, key) -> dict: 
        async with DefaultAzureCredential() as credential:    
            async with CosmosClient(self.db_uri, credential=credential) as db_client:
                db = db_client.get_database_client(database=self.db_name)
                container = db.get_container_client(container)
                try:
                    document = await container.create_item(body={"id": key})                    
                    logging.info(f"[cosmosdb] document {key} created.")
                except Exception as e:
                    document = None
                    logging.info(f"[cosmosdb] error creating document {key}. Error: {e}")
                return document
            
    async def update_document(self, container, document) -> dict: 
        async with DefaultAzureCredential() as credential:    
            async with CosmosClient(self.db_uri, credential=credential) as db_client:
                db = db_client.get_database_client(database=self.db_name)
                container = db.get_container_client(container)
                try:
                    document = await container.replace_item(item=document, body=document)
                    logging.info(f"[cosmosdb] document updated.")
                except Exception as e:
                    document = None
                    logging.info(f"[cosmosdb] could not update document.")
                return document
            