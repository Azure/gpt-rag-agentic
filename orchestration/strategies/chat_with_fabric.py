import json
import logging
import os
import sqlparse
from pydantic import BaseModel, Field
from typing import Annotated, Dict, List, Optional, Union

from autogen_agentchat.agents import AssistantAgent
from .base_agent_strategy import BaseAgentStrategy
from tools import get_time, get_today_date, queries_retrieval
from connectors import SQLEndpointClient, SemanticModelClient
from ..constants import CHAT_WITH_FABRIC

## Types

class DataSourcesList(BaseModel):
    datasources: List[Dict[str, Union[str, List[str]]]]

class SchemaInfo(BaseModel):
    source: Optional[str] = None
    table_name: Optional[str] = None
    description: Optional[str] = None
    columns: Optional[Dict[str, str]] = None
    error: Optional[str] = None

class TablesList(BaseModel):
    tables: List[Dict[str, Union[str, List[str]]]]
    error: Optional[str] = None

class ValidateSQLResult(BaseModel):
    is_valid: bool
    error: Optional[str] = None

class ExecuteQueryResult(BaseModel):
    results: Optional[List[Dict[str, Union[str, int, float, None]]]] = None
    error: Optional[str] = None

## Agent Strategy

class ChatWithFabricStrategy(BaseAgentStrategy):
    def __init__(self):

        # Initialize the strategy type
        super().__init__()
        self.strategy_type = CHAT_WITH_FABRIC

        # Load configurations
        self.data_dictionary = self._load_config('config/fabric/data_dictionary.json')
        self.data_sources = self._load_config('config/fabric/data_sources.json')

    async def create_agents(self, llm_config, history, client_principal=None):

        self.max_rounds = 5      
        conversation_summary = await self._summarize_conversation(history)

        ## Wrapper Functions for Tools

        def get_all_datasources_info() -> DataSourcesList:
            return self._get_all_datasources_info()

        def get_all_tables_info(database_name: Annotated[str, Field(description="Name of the target database")]) -> TablesList:
            return self._get_all_tables_info(database_name)

        def get_schema_info(
            database_name: Annotated[str, Field(description="Name of the target database")],
            table_name: Annotated[str, Field(description="Name of the target table")],
            column_name: Optional[
                Annotated[str, Field(description="Name of the specific column (optional)")]
            ] = None
        ) -> SchemaInfo:
            return self._get_schema_info(database_name, table_name, column_name)

        async def execute_dax_query(
            database_name: Annotated[str, Field(description="Name of the target database")],
            query: Annotated[str, Field(description="DAX query to be executed")]
        ) -> ExecuteQueryResult:
            return await self._execute_dax_query(database_name, query)

        def validate_sql_query(
            query: Annotated[str, Field(description="SQL query to be validated")]
        ) -> ValidateSQLResult:
            return self._validate_sql_query(query)

        async def execute_sql_query(
            database_name: Annotated[str, Field(description="Name of the target database")],
            query: Annotated[str, Field(description="SQL query to be executed")]
        ) -> ExecuteSQLResult:
            return await self._execute_sql_query(database_name, query)
        
        
        ## Agents

        # Triage Agent
        triage_prompt = await self._read_prompt("triage_agent", {"conversation_summary": conversation_summary})
        triage_agent = AssistantAgent(
            name="Triage Agent",
            system_message=triage_prompt,
            model_client=self._get_model_client(), 
            tools=[get_all_datasources_info, get_today_date, get_time],
            reflect_on_tool_use=True
        )

        # DAX Query Agent
        dax_query_prompt = await self._read_prompt("dax_query_agent", {"conversation_summary": conversation_summary})        
        dax_query_agent = AssistantAgent(
            name="DAX Query Agent",
            system_message=dax_query_prompt,
            model_client=self._get_model_client(), 
            tools=[get_all_tables_info, get_schema_info, queries_retrieval, execute_dax_query, get_today_date, get_time],
            reflect_on_tool_use=True
        )

        # SQL Query Agent 
        sql_query_prompt = await self._read_prompt("sql_query_agent", {"conversation_summary": conversation_summary})             
        sql_query_agent = AssistantAgent(
            name="SQL Query Agent ",
            system_message=sql_query_prompt,
            model_client=self._get_model_client(), 
            tools=[get_all_tables_info, get_schema_info, queries_retrieval, validate_sql_query, execute_sql_query, get_today_date, get_time],
            reflect_on_tool_use=True
        )        

        # Chat Closure Agent
        chat_closure_prompt = await self._read_prompt("chat_closure", {"conversation_summary": conversation_summary})
        chat_closure = AssistantAgent(
            name="Chat Closure Agent",
            system_message=chat_closure_prompt,
            model_client=self._get_model_client(),
            reflect_on_tool_use=True
        )

        ## Group Chat Configuration

        def custom_selector_func(messages):
            """
            Selects the next agent based on the source of the last message.
            
            Transition Rules:
               user -> Triage Agent
               Triage Agent -> None (SelectorGroupChat will handle transition)
            """
            last_msg = messages[-1]
            if last_msg.source == "user":
                return "Triage Agent"
            else:
                return None
            
        self.selector_func = custom_selector_func

        self.agents = [triage_agent, dax_query_agent, sql_query_agent, chat_closure]

        return self._get_agent_configuration()

    ## Tools Implementation

    def _get_all_datasources_info(self) -> DataSourcesList:
        """
        Retrieve a list of all data sources with their descriptions and other attributes from the data source config.
        """
        datasources_info = []
        for datasource_name, datasource_info in self.data_sources.items():
            datasources_info.append({
                'datasource': datasource_name,
                'description': datasource_info.get("description"),
                'type': datasource_info.get("type"),
                'database': datasource_info.get("database")
            })

        return DataSourcesList(datasources=datasources_info)

    def _get_all_tables_info(self, datasource: str) -> TablesList:
        """
        Retrieve a list of database tables with their descriptions from the data dictionary,
        filtering only the tables where the datasource matches the provided database parameter.
        
        If no tables are found for the given datasource, returns a TablesList with an error message.
        """
        tables_info = [
            {
                'table_name': table_name,
                'description_long': table_info.get("description")
            }
            for table_name, table_info in self.data_dictionary.items()
            if table_info.get("datasource") == datasource
        ]
        
        if not tables_info:
            return TablesList(
                tables=[],
                error=f"No datasource with name '{datasource}' was found."
            )
        
        return TablesList(tables=tables_info)
    
    def _get_schema_info(self, datasource, table_name=None, column_name=None) -> SchemaInfo:
        """
        Retrieve schema information from the data dictionary based on the datasource.
        
        Parameters:
            datasource (str): The name of the datasource.
            table_name (str, optional): The name of the table to retrieve information for.
            column_name (str, optional): The name of the column to retrieve information for.
            
        Returns:
            SchemaInfo: An object containing the schema information or an error message.
        """
        # Check if the datasource exists
        datasource_info = self.data_dictionary.get(datasource)
        if not datasource_info:
            return SchemaInfo(error=f"Datasource '{datasource}' not found in data dictionary.")

        if table_name:
            table_info = datasource_info.get(table_name)
            if table_info:
                return SchemaInfo(
                    datasource_name=datasource,
                    table_name=table_name,
                    description_long=table_info.get("description_long"),
                    description_short=table_info.get("description_short"),
                    columns=table_info.get("columns")
                )
            else:
                return SchemaInfo(error=f"Table '{table_name}' not found in datasource '{datasource}'.")
        
        elif column_name:
            for table, info in datasource_info.items():
                columns = info.get("columns", {})
                if column_name in columns:
                    return SchemaInfo(
                        datasource_name=datasource,
                        table_name=table,
                        column_name=column_name,
                        column_description=columns[column_name]
                    )
            return SchemaInfo(error=f"Column '{column_name}' not found in datasource '{datasource}'.")
        
        else:
            # If neither table_name nor column_name is provided, list all tables
            tables = list(datasource_info.keys())
            return SchemaInfo(
                datasource_name=datasource,
                tables=tables
            )

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

    # TODO: Implement this
    async def _execute_dax_query(self, database_name: str, query: str) -> ExecuteQueryResult:
        """
        Execute an DAX query and return the results.
        Returns a list of dictionaries, each representing a row.
        """
        try:
            semantic_model_client = SemanticModelClient()
            query_results = await semantic_model_client.execute(query)
            columns = [column[0] for column in query_results.description]
            rows = query_results.fetchall()
            results = [dict(zip(columns, row)) for row in rows]
            return ExecuteQueryResult(results=results)
        except Exception as e:
            return ExecuteQueryResult(error=str(e))
    
    # TODO: Implement this
    async def _execute_sql_query(self, database_name: str, query: str) -> ExecuteQueryResult:
        """
        Execute an SQL query and return the results.
        Returns a list of dictionaries, each representing a row.
        """
        try:
            sql_client = SQLEndpointClient()
            connection = await sql_client.create_connection()
            cursor = connection.cursor()

            if not query.strip().lower().startswith('select'):
                return ExecuteQueryResult(error="Only SELECT statements are allowed.")

            cursor.execute(query)
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            results = [dict(zip(columns, row)) for row in rows]
            return ExecuteQueryResult(results=results)
        except Exception as e:
            return ExecuteQueryResult(error=str(e))

    # Utility methods

    def _load_config(self, file_path):
        """Helper method to load configuration files with logging and error handling."""
        config_name = os.path.splitext(os.path.basename(file_path))[0]  # Infer from file name
        if os.path.exists(file_path):
            logging.info(f"[chat_with_fabric] Using {config_name}: {file_path}")
            with open(file_path, 'r') as file:
                return json.load(file)
        else:
            error_message = f"[chat_with_fabric] {config_name} file not found: {file_path}"
            logging.error(error_message)
            raise FileNotFoundError(error_message)
