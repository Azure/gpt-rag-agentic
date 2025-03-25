import os

from pydantic import BaseModel

from autogen_agentchat.agents import AssistantAgent
from autogen_core.tools import FunctionTool

from .nl2sql_base_agent_strategy import NL2SQLBaseStrategy
from ..constants import Strategy
from tools import (
    get_time,
    get_today_date,
    get_all_datasources_info,
    get_all_tables_info,
    get_schema_info,
    validate_sql_query,
    execute_sql_query,
)

# Agents Strategy Class

class NL2SQLStandardStrategy(NL2SQLBaseStrategy):

    def __init__(self):
        self.strategy_type = Strategy.NL2SQL
        super().__init__()

    async def create_agents(self, history, client_principal=None, access_token=None, output_mode=None, output_format=None):
        """
        Creates agents and registers functions for the NL2SQL single agent scenario.
        """

        # Model Context
        shared_context = await self._get_model_context(history) 

        ## Wrapper Functions for Tools

        get_all_datasources_info_tool = FunctionTool(
            get_all_datasources_info, description="Retrieve a list of all datasources."
        )

        get_all_tables_info_tool = FunctionTool(
            get_all_tables_info, description="Retrieve a list of tables filtering by the given datasource."
        )

        get_schema_info_tool = FunctionTool(
            get_schema_info, description="Retrieve information about tables and columns from the data dictionary."
        )        

        validate_sql_query_tool = FunctionTool(
            validate_sql_query, description="Validate the syntax of an SQL query."
        )     

        execute_sql_query_tool = FunctionTool(
            execute_sql_query, description="Execute an SQL query and return the results."
        )

        ## Agents

        # Assistant Agent
        sql_agent_prompt = await self._read_prompt("nl2sql_assistant")
        sql_agent = AssistantAgent(
            name="sql_agent",
            system_message=sql_agent_prompt,
            model_client=self._get_model_client(), 
            tools=[get_all_datasources_info_tool, get_schema_info_tool, validate_sql_query_tool, get_all_tables_info_tool, execute_sql_query_tool, get_today_date, get_time],
            reflect_on_tool_use=True,
            model_context=shared_context
        )

        ## Chat Closure Agent
        chat_closure = await self._create_chat_closure_agent(output_format, output_mode)

        # Group Chat Configuration
        self.max_rounds = int(os.getenv('MAX_ROUNDS', 20))

        def custom_selector_func(messages):
            """
            Selects the next agent based on the source of the last message.
            
            Transition Rules:
               user -> sql_agent
               sql_agent -> None (SelectorGroupChat will handle transition)
            """
            last_msg = messages[-1]
            if last_msg.source == "user":
                return "sql_agent"
            else:
                return None                  
        
        self.selector_func = custom_selector_func

        self.agents = [sql_agent, chat_closure]
        
        return self._get_agents_configuration()