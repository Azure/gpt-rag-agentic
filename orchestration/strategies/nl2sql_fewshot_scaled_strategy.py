import os
from pydantic import BaseModel
from autogen_agentchat.agents import AssistantAgent
from autogen_core.tools import FunctionTool
from .nl2sql_base_agent_strategy import NL2SQLBaseStrategy
from tools import (
    get_time,
    get_today_date,
    queries_retrieval,
    tables_retrieval,
    columns_retrieval,
    get_all_datasources_info,
    get_all_tables_info,
    get_schema_info,
    execute_dax_query,
    validate_sql_query,
    execute_sql_query,
)

## Group Chat Response Format

class ChatGroupResponse(BaseModel):
    answer: str
    reasoning: str

# Agents Strategy Class

class NL2SQLFewshotScaledStrategy(NL2SQLBaseStrategy):

    def __init__(self):
        self.strategy_type = "nl2sql_fewshot_scaled"
        super().__init__()

    async def create_agents(self, history, client_principal=None):
        """
        Creates agents and registers functions for the NL2SQL single agent scenario.
        """
      
        # Wrapper Functions for Tools

        get_all_datasources_info_tool = FunctionTool(
            get_all_datasources_info, description="Retrieve a list of all datasources."
        )

        get_all_tables_info_tool = FunctionTool(
            get_all_tables_info, description="Retrieve a list of tables filtering by the given datasource."
        )

        get_schema_info_tool = FunctionTool(
            get_schema_info, description="Retrieve information about tables and columns from the data dictionary."
        )        

        queries_retrieval_tool = FunctionTool(
            queries_retrieval, description="Retrieve a list of similar questions and the correspondent query, selected_tables, selected_columns and reasoning."
        )

        tables_retrieval_tool = FunctionTool(
            tables_retrieval, description="Retrieves necessary tables from the retrieval system based on the input query to build a response for the user's request"
        )

        columns_retrieval_tool = FunctionTool(
            columns_retrieval, description="Retrieves necessary columns for a specific table from the retrieval system based on the user's query to build a response."
        )                

        execute_dax_query_tool = FunctionTool(
            execute_dax_query, description="Execute an DAX query and return the results."
        )     

        validate_sql_query_tool = FunctionTool(
            validate_sql_query, description="Validate the syntax of an SQL query."
        )     

        execute_sql_query_tool = FunctionTool(
            execute_sql_query, description="Execute an SQL query and return the results."
        )

        # Model Context
        shared_context = await self._get_model_context(history) 

        # Agents

        ## Assistant Agent
        assistant_prompt = await self._read_prompt("nl2sql_assistant")
        assistant = AssistantAgent(
            name="assistant",
            system_message=assistant_prompt,
            model_client=self._get_model_client(), 
            tools=[get_all_datasources_info_tool, validate_sql_query_tool, queries_retrieval_tool, tables_retrieval_tool, columns_retrieval_tool, execute_sql_query_tool, get_today_date, get_time],
            reflect_on_tool_use=True,
            model_context=shared_context
        )

        ## Chat closure agent
        chat_closure_prompt = await self._read_prompt("chat_closure")
        chat_closure = AssistantAgent(
            name="chat_closure",
            system_message=chat_closure_prompt,
            model_client=self._get_model_client(response_format=ChatGroupResponse)
        )

        # Group Chat Configuration

        self.max_rounds = int(os.getenv('MAX_ROUNDS', 30))

        def custom_selector_func(messages):
            """
            Selects the next agent based on the source of the last message.
            
            Transition Rules:
               user -> assistant
               assistant -> None (SelectorGroupChat will handle transition)
            """
            last_msg = messages[-1]
            if last_msg.source == "user":
                return "assistant"
            else:
                return None     
        
        self.selector_func = custom_selector_func

        # Return agent configuration
        self.agents = [assistant, chat_closure]
        
        return self._get_agent_configuration()
