import os
import logging
import pyodbc
import struct
from azure.identity import ManagedIdentityCredential, AzureCliCredential, ChainedTokenCredential
from .keyvault import get_secret

# TODO: Review this class implementation based on the reference and instrcutions provided in the task
class SQLDBClient:
    def __init__(self, datasource_config):
        self.datasource_config = datasource_config
        pass

    async def create_connection(self):
        return await self._create_sqldatabase_connection()

    async def _create_sqldatabase_connection(self):
        # TODO: dont use env variables anymore, use the configuration from cosmosdb
        server = os.environ.get('SQL_DATABASE_SERVER', 'replace_with_database_server_name')
        database = os.environ.get('SQL_DATABASE_NAME', 'replace_with_database_name')
        uid = os.environ.get('SQL_DATABASE_UID', None)
        pwd = None
        if uid:
            pwd = await get_secret('sqlDatabasePassword')

        connection_string = (
                f"Driver={{ODBC Driver 18 for SQL Server}};"
                f"Server={server},1433;"
                f"Database={database};"
                "Encrypt=yes;"
                "TrustServerCertificate=no;"
                "Connection Timeout=30;"
            )

        # If UID and password are provided, use SQL Server authentication
        if uid and pwd:
            connection_string += f"UID={uid};PWD={pwd};"
            logging.info("Using SQL Server authentication.")
            try:
                connection = pyodbc.connect(connection_string)
                return connection
            except Exception as e:
                logging.error(f"Failed to connect to the database with SQL Server authentication: {e}")
                raise
        else:
            # Use Azure AD token for authentication
            credential = ChainedTokenCredential(
                ManagedIdentityCredential(),
                AzureCliCredential()
            )
            token_bytes = credential.get_token("https://database.windows.net/.default").token.encode("UTF-16-LE")
            token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
            logging.info("Using Azure AD token authentication.")
            try:
                SQL_COPT_SS_ACCESS_TOKEN = 1256
                connection = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
                return connection
            except Exception as e:
                logging.error(f"Failed to connect to the database with Azure AD token authentication: {e}")
                raise