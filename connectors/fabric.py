import logging
import pyodbc
from .keyvault import get_secret

class SQLEndpointClient:
    def __init__(self, datasource_config):
        self.datasource_config = datasource_config
        pass

    async def create_connection(self):
        return await self._create_sqlendpoint_connection()

    async def _create_sqlendpoint_connection(self):
        server = self.datasource_config['server']
        database = self.datasource_config['database']
        client_id = self.datasource_config['client_id']
        tenant_id = self.datasource_config['tenant_id']
        service_principal_id = f"{client_id}@{tenant_id}"
        kv_secret_name = f"{self.datasource_config['service_principal']}-secret"
        client_secret = await get_secret(kv_secret_name)

        connection_string = (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={service_principal_id};"
            f"PWD={client_secret};"
            f"Authentication=ActiveDirectoryServicePrincipal"
        
        )
        try:
            connection = pyodbc.connect(connection_string)
            return connection
        except Exception as e:
            logging.error(f"Failed to connect to the database with service principal: {e}")
            raise

class SemanticModelClient:
    def __init__(self, datasource_config):
        self.datasource_config = datasource_config
        pass

    async def create_connection(self):
        return await self._create_semantic_model_connection()

    async def _create_semantic_model_connection(self):
        # TODO: Implement this method based on the reference and instrcutions provided in the task
        pass