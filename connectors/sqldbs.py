import asyncio
import logging
import pyodbc
import struct
from azure.identity import ManagedIdentityCredential, AzureCliCredential, ChainedTokenCredential
from connectors.keyvault import get_secret, generate_valid_secret_name
from connectors.types import SQLDatabaseConfig

class SQLDBClient:
    """
    Client for connecting to a Fabric SQL Database using either SQL Server authentication
    (with a UID and password stored in Key Vault) or Managed Identity.
    """
    def __init__(self, datasource_config):
        if not isinstance(datasource_config, SQLDatabaseConfig):
            datasource_config = SQLDatabaseConfig.model_validate(datasource_config)
        self.datasource_config = datasource_config

    async def create_connection(self):
        return await self._create_sqldatabase_connection()

    async def _create_sqldatabase_connection(self):
        server = self.datasource_config.server
        database = self.datasource_config.database
        uid = self.datasource_config.uid
        connection_string = (
            f"Driver={{ODBC Driver 18 for SQL Server}};"
            f"Server={server},1433;"
            f"Database={database};"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
            "Connection Timeout=30;"
        )

        if uid:
            kv_secret_name = generate_valid_secret_name(f"{self.datasource_config.id}-secret")
            # Retrieve SQL user password from Key Vault using datasource id.
            pwd = await get_secret(kv_secret_name)
            connection_string += f"UID={uid};PWD={pwd};"
            logging.info("Using SQL Server authentication for SQL Database.")
            try:
                connection = await asyncio.to_thread(pyodbc.connect, connection_string)
                return connection
            except Exception as e:
                logging.error(f"Failed to connect to SQL Database with SQL Server authentication: {e}")
                raise
        else:
            # Use Azure AD token for authentication via Managed Identity.
            credential = ChainedTokenCredential(
                ManagedIdentityCredential(),
                AzureCliCredential()
            )
            try:
                token = credential.get_token("https://database.windows.net/.default")
                token_bytes = token.token.encode("UTF-16-LE")
                token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
                SQL_COPT_SS_ACCESS_TOKEN = 1256
                connection = await asyncio.to_thread(
                    pyodbc.connect,
                    connection_string,
                    attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct}
                )
                logging.info("Using Azure AD token authentication for SQL Database.")
                return connection
            except Exception as e:
                logging.error(f"Failed to connect to SQL Database with Azure AD token authentication: {e}")
                raise
