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
    def create_connection(self):
        database_type = os.environ.get('SQL_DATABASE_TYPE', 'sqldatabase').lower()

        if database_type == 'fabric':
            return self._create_fabric_connection()
        elif database_type == 'sqldatabase':
            return self._create_sqldatabase_connection()
        elif database_type == 'teradata':
            return self._create_teradata_connection()
        else:
            raise ValueError(f"Unsupported database type: {database_type}")

    def _create_sqldatabase_connection(self):
        server = os.environ.get('SQL_DATABASE_SERVER', 'replace_with_database_server_name')
        database = os.environ.get('SQL_DATABASE_NAME', 'replace_with_database_name')

        # Obtain token using DefaultAzureCredential
        credential = DefaultAzureCredential()
        token_bytes = credential.get_token("https://database.windows.net/.default").token.encode("UTF-16-LE")
        token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
        connection_string = (
            f"Driver={{ODBC Driver 18 for SQL Server}};"
            f"Server={server},1433;"
            f"Database={database};"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
            "Connection Timeout=30"
        )
        try:
            SQL_COPT_SS_ACCESS_TOKEN = 1256
            connection = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
            return connection
        except Exception as e:
            logging.error(f"Failed to connect to default database: {e}")
            raise

    def _create_fabric_connection(self):
        server = os.environ.get('SQL_DATABASE_SERVER', 'replace_with_database_server_name')
        database = os.environ.get('SQL_DATABASE_NAME', 'replace_with_database_name')

        # Obtain token using DefaultAzureCredential
        credential = DefaultAzureCredential()
        token_bytes = credential.get_token("https://database.windows.net/.default").token.encode("UTF-16-LE")
        token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
        connection_string = (
            f"Driver={{ODBC Driver 18 for SQL Server}};"
            f"Server={server},1433;"
            f"Database={database};"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
            "Connection Timeout=30"
        )
        try:
            SQL_COPT_SS_ACCESS_TOKEN = 1256
            connection = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
            return connection
        except Exception as e:
            logging.error(f"Failed to connect to Fabric database: {e}")
            raise

    def _create_teradata_connection(self):
        host = os.environ.get('TD_HOST', 'replace_with_teradata_hostname')
        user = os.environ.get('TD_USER', 'replace_with_user_name')
        password = get_secret('TD_PASSWORD')

        if not all([host, user, password]):
            raise ValueError("Missing required Teradata connection parameters: 'host', 'user', 'password'")

        connection_string = f'{{"host":"{host}","user":"{user}","password":"{password}"}}'

        try:
            connection = teradatasql.connect(connection_string)
            return connection
        except Exception as e:
            logging.error(f"Failed to connect to Teradata database: {e}")
            raise
