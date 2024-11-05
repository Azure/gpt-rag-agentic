import os
import logging
import pyodbc
import struct
import teradatasql 
from azure.identity import DefaultAzureCredential
from .keyvault import get_secret

class SQLDBClient:
    def __init__(self):
        pass
    async def create_connection(self):
        database_type = os.environ.get('SQL_DATABASE_TYPE', 'sqldatabase').lower()
        if database_type == 'fabric':
            return await self._create_fabric_connection()
        elif database_type == 'sqldatabase':
            return await self._create_sqldatabase_connection()
        elif database_type == 'teradata':
            return await self._create_teradata_connection()
        else:
            raise ValueError(f"Unsupported database type: {database_type}")

    async def _create_sqldatabase_connection(self):
        server = os.environ.get('SQL_DATABASE_SERVER', 'replace_with_database_server_name')
        database = os.environ.get('SQL_DATABASE_NAME', 'replace_with_database_name')
        uid = os.environ.get('SQL_DATABASE_UID', None)
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
            credential = DefaultAzureCredential()
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


    async def _create_fabric_connection(self):
        server = os.environ.get('SQL_DATABASE_SERVER', 'fabric_endpoint_connection_string')
        database = os.environ.get('SQL_DATABASE_NAME', 'fabric_lakehouse_or_warehouse_name')
        # TODO: Use service principal for Fabric Authentication
        # https://learn.microsoft.com/en-us/fabric/data-warehouse/entra-id-authentication#microsoft-odbc-driver
        # service_principal_id = f"{client_id}@{tenant_id}"        
        uid = None
        pwd = None

        # Obtain token using DefaultAzureCredential
        credential = DefaultAzureCredential()
        token_bytes = credential.get_token("https://database.windows.net/.default").token.encode("UTF-16-LE")
        token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
        connection_string = (
            f"Driver={{ODBC Driver 18 for SQL Server}};"
            f"Server={server},1433;"
            f"Database={database};"
            f"UID={uid};"
            f"PWD={pwd};"                        
            f"Authentication=ActiveDirectoryServicePrincipal;"
            "TrustServerCertificate=no;"
            "Connection Timeout=30"
        )
        try:
            connection = pyodbc.connect(connection_string)
            return connection
        except Exception as e:
            logging.error(f"Failed to connect to Fabric database: {e}")
            raise

    async def _create_teradata_connection(self):
        host = os.environ.get('TD_HOST', 'replace_with_teradata_hostname')
        user = os.environ.get('TD_USER', 'replace_with_user_name')
        password = get_secret('teradataPassword')

        if not all([host, user, password]):
            raise ValueError("Missing required Teradata connection parameters: 'host', 'user', 'password'")

        connection_string = f'{{"host":"{host}","user":"{user}","password":"{password}"}}'

        try:
            connection = teradatasql.connect(connection_string)
            return connection
        except Exception as e:
            logging.error(f"Failed to connect to Teradata database: {e}")
            raise
