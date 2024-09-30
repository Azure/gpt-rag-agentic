import os
import logging
import pyodbc
import struct
from azure.identity import DefaultAzureCredential


class SQLDBClient:
    def __init__(self, sql_config):
        self.sql_config = sql_config

    def create_connection(self):
        database_type = os.environ.get('SQL_DATABASE_TYPE', 'sqldatabase')

        if database_type.lower() == 'fabric':
            return self._create_fabric_connection()
        elif database_type.lower() == 'sqldatabase':
            return self._create_sqldatabase_connection()
        else:
            raise ValueError(f"Unsupported database type: {database_type}")

    def _create_sqldatabase_connection(self):
        server = self.sql_config['server']
        database = self.sql_config['database']

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
        server = self.sql_config['server']
        database = self.sql_config['database']

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