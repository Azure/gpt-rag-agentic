import logging
import json
import os
import sqlparse
from abc import ABC, abstractmethod
from connectors.sqldbs import SQLDBClient
from .base_agent_strategy import BaseAgentStrategy
from typing import Optional, List, Dict, Union
from pydantic import BaseModel

class SchemaInfo(BaseModel):
    table_name: Optional[str] = None
    description_long: Optional[str] = None
    description_short: Optional[str] = None
    columns: Optional[Dict[str, str]] = None
    column_name: Optional[str] = None
    column_description: Optional[str] = None
    error: Optional[str] = None

class TablesList(BaseModel):
    tables: List[Dict[str, Union[str, List[str]]]]

class ValidateSQLResult(BaseModel):
    is_valid: bool
    error: Optional[str] = None

class ExecuteSQLResult(BaseModel):
    results: Optional[List[Dict[str, Union[str, int, float, None]]]] = None
    error: Optional[str] = None

class NL2SQLBaseStrategy(BaseAgentStrategy, ABC):

    def __init__(self):
        super().__init__()
        # Subclasses should set self.strategy_type

        # Load the data dictionary JSON file
        custom_data_dictionary_path = 'config/data_dictionary.custom.json'
        default_data_dictionary_path = 'config/data_dictionary.json'

        # Check for the custom data dictionary file first
        if os.path.exists(custom_data_dictionary_path):
            data_dictionary_path = custom_data_dictionary_path
            logging.info(f"[data_dictionary] Using custom data dictionary: {custom_data_dictionary_path}")
        elif os.path.exists(default_data_dictionary_path):
            data_dictionary_path = default_data_dictionary_path
            logging.info(f"[data_dictionary] Using default data dictionary: {default_data_dictionary_path}")
        else:
            logging.error("[data_dictionary] Data dictionary file not found.")
            raise FileNotFoundError("Data dictionary file not found.")

        with open(data_dictionary_path, 'r') as f:
            self.data_dictionary = json.load(f)

    async def create_connection(self):
        connector = SQLDBClient()
        connection = await connector.create_connection()
        return connection

    @property
    @abstractmethod
    def max_rounds(self):
        pass

    @property
    @abstractmethod
    def send_introductions(self):
        pass
    
    @abstractmethod
    def create_agents(self, llm_config, history, client_principal=None):
        pass

    # Helper methods that can be used by subclasses
    def _get_schema_info(self, table_name=None, column_name=None) -> SchemaInfo:
        """
        Retrieve schema information from the data dictionary.
        If table_name is provided, returns the table description and columns.
        If column_name is provided, returns the column description.
        """
        if table_name:
            table_info = self.data_dictionary.get(table_name)
            if table_info:
                return SchemaInfo(
                    table_name=table_name,
                    description_long=table_info.get("description_long"),
                    description_short=table_info.get("description_short"),
                    columns=table_info.get("columns")
                )
            else:
                return SchemaInfo(error=f"Table '{table_name}' not found in data dictionary.")
        elif column_name:
            for table, info in self.data_dictionary.items():
                columns = info["columns"]
                if column_name in columns:
                    return SchemaInfo(
                        table_name=table,
                        column_name=column_name,
                        column_description=columns[column_name]
                    )
            return SchemaInfo(error=f"Column '{column_name}' not found in data dictionary.")
        else:
            return SchemaInfo(error="Please provide either 'table_name' or 'column_name'.")

    def _get_all_tables_info(self) -> TablesList:
        """
        Retrieve a list of all tables with their descriptions from the data dictionary.
        """
        tables_info = []
        for table_name, table_info in self.data_dictionary.items():
            tables_info.append({
                'table_name': table_name,
                'description_long': table_info.get("description_long")
            })
        return TablesList(tables=tables_info)

    def _validate_sql_query(self, query: str) -> ValidateSQLResult:
        """
        Validate the syntax of an SQL query.
        Returns {'is_valid': True} if valid, or {'is_valid': False, 'error': 'error message'} if invalid.
        """
        try:
            parsed = sqlparse.parse(query)
            if parsed and len(parsed) > 0:
                return ValidateSQLResult(is_valid=True)
            else:
                return ValidateSQLResult(is_valid=False, error="Query could not be parsed.")
        except Exception as e:
            return ValidateSQLResult(is_valid=False, error=str(e))

    async def _execute_sql_query(self, query: str) -> ExecuteSQLResult:
        """
        Execute an SQL query and return the results.
        Returns a list of dictionaries, each representing a row.
        """
        try:
            connection = await self.create_connection()
            cursor = connection.cursor()

            if not query.strip().lower().startswith('select'):
                return ExecuteSQLResult(error="Only SELECT statements are allowed.")

            cursor.execute(query)
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            results = [dict(zip(columns, row)) for row in rows]
            return ExecuteSQLResult(results=results)
        except Exception as e:
            return ExecuteSQLResult(error=str(e))