import logging
import json
import os
import sqlparse
import pyodbc, struct
from azure.identity import DefaultAzureCredential
from autogen import UserProxyAgent, AssistantAgent, register_function
from .base_agent_creation_strategy import BaseAgentCreationStrategy
from .constants import NL2SQL_DUO
from typing import Optional, List, Dict, Union
from pydantic import BaseModel

# Define Pydantic models for the return types
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

class NL2SQLDuoAgentCreationStrategy(BaseAgentCreationStrategy):

    def __init__(self):
        super().__init__()
        self.strategy_type = NL2SQL_DUO

        # Load the data dictionary JSON file
        data_dictionary_path = 'config/data_dictionary.json'
        with open(data_dictionary_path, 'r') as f:
            self.data_dictionary = json.load(f)

        # Initialize the database connection
        self.sql_config = {
            'server': os.environ.get('SQL_DATABASE_SERVER', 'replace_with_database_server_name'),
            'database': os.environ.get('SQL_DATABASE_NAME', 'replace_with_database_name')
        }
        self.connection = self.create_connection()
        self.cursor = self.connection.cursor()
    
    @property
    def max_rounds(self):
        return 30      

    def create_connection(self):

        server = self.sql_config['server']
        database = self.sql_config['database']

        # Obtain token using DefaultAzureCredential
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        token_bytes = credential.get_token("https://database.windows.net/.default").token.encode("UTF-16-LE")
        token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
        connection_string = f"Driver={{ODBC Driver 18 for SQL Server}};Server=tcp:{server},1433;Database={database};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30"

        try:
            # Establish a connection using the token
            SQL_COPT_SS_ACCESS_TOKEN = 1256  # This connection option is defined by Microsoft in msodbcsql.h
            connection = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
            return connection
        except Exception as e:
            logging.error(f"Failed to connect to database: {e}")
            raise
    
    def create_agents(self, llm_config, history):
        """
        Creates agents and registers functions for the NL2SQL scenario.
        """

        # Create User Proxy Agent
        user_proxy_prompt = self._read_prompt("user_proxy")
        user_proxy = UserProxyAgent(
            name="user",
            system_message=user_proxy_prompt,
            human_input_mode="NEVER",
            code_execution_config=False,
            is_termination_msg=lambda msg: msg.get("content") is not None and "TERMINATE" in msg["content"]
        )

        # Create Assistant Agent
        conversation_summary = self._summarize_conversation(history)
        assistant_prompt = self._read_prompt("nl2sql_assistant", {"conversation_summary": conversation_summary})
        assistant = AssistantAgent(
            name="assistant",
            description="Interpret user request, generate and validate SQL, execute, and deliver clear results",
            system_message=assistant_prompt,
            human_input_mode="NEVER",
            llm_config=llm_config,
            is_termination_msg=lambda msg: msg.get("content") is not None and "TERMINATE" in msg["content"]            
        )

        # Create Reviewer Agent
        reviewer_prompt = self._read_prompt("reviewer")
        reviewer = AssistantAgent(
            name="reviewer",
            description="Ensure SQL queries and responses are accurate, efficient, and relevant, approving or suggesting improvements.",
            system_message=reviewer_prompt,
            human_input_mode="NEVER",
            llm_config=llm_config
        )

        # Define functions inside create_agents to access instance variables and add type annotations
        def get_schema_info(table_name: Optional[str] = None, column_name: Optional[str] = None) -> SchemaInfo:
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
                # Search all tables for the column
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

        def get_all_tables_info() -> TablesList:
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

        def validate_sql_query(query: str) -> ValidateSQLResult:
            """
            Validate the syntax of an SQL query.
            Returns {'is_valid': True} if valid, or {'is_valid': False, 'error': 'error message'} if invalid.
            """
            try:
                parsed = sqlparse.parse(query)
                if parsed and len(parsed) > 0:
                    # Additional checks can be added here if needed
                    return ValidateSQLResult(is_valid=True)
                else:
                    return ValidateSQLResult(is_valid=False, error="Query could not be parsed.")
            except Exception as e:
                return ValidateSQLResult(is_valid=False, error=str(e))

        def execute_sql_query(query: str) -> ExecuteSQLResult:
            """
            Execute an SQL query and return the results.
            Returns a list of dictionaries, each representing a row.
            """
            try:
                # Limit to SELECT statements only for safety
                if not query.strip().lower().startswith('select'):
                    return ExecuteSQLResult(error="Only SELECT statements are allowed.")

                self.cursor.execute(query)
                columns = [column[0] for column in self.cursor.description]
                rows = self.cursor.fetchall()
                results = [dict(zip(columns, row)) for row in rows]
                return ExecuteSQLResult(results=results)
            except Exception as e:
                return ExecuteSQLResult(error=str(e))

        # Register functions with type annotations
        register_function(
            get_all_tables_info,
            caller=assistant,
            executor=user_proxy,
            name="get_all_tables_info",
            description="Retrieve a list of all table names and their descriptions from the data dictionary."
        )

        register_function(
            get_schema_info,
            caller=assistant,
            executor=user_proxy,
            name="get_schema_info",
            description="Retrieve schema information from the data dictionary. Provide table_name or column_name to get information about the table or column."
        )

        register_function(
            validate_sql_query,
            caller=assistant,
            executor=user_proxy,
            name="validate_sql_query",
            description="Validate the syntax of an SQL query. Returns is_valid as True if valid, or is_valid as False with an error message if invalid."
        )

        register_function(
            execute_sql_query,
            caller=assistant,
            executor=user_proxy,
            name="execute_sql_query",
            description="Execute an SQL query and return the results as a list of dictionaries. Each dictionary represents a row."
        )

        return [user_proxy, assistant, reviewer]
