import os

from typing import List, Optional
from pydantic import BaseModel

from autogen_agentchat.agents import AssistantAgent
from autogen_core.tools import FunctionTool

from .base_agent_strategy import BaseAgentStrategy
from ..constants import CHAT_WITH_FABRIC
from tools import (
    get_time,
    get_today_date,
    queries_retrieval,
    get_all_datasources_info,
    get_all_tables_info,
    get_schema_info,
    execute_dax_query,
    validate_sql_query,
    execute_sql_query,
)

## Agent Response Types

class ChatGroupResponse(BaseModel):
    answer: str
    thoughts: str

class DataSource(BaseModel):
    name: str
    description: str

class TriageAgentResponse(BaseModel):
    answer: str
    datasources: Optional[List[DataSource]]

# Agents Strategy Class

class ChatWithFabricStrategy(BaseAgentStrategy):
     
    def __init__(self):
        # Initialize the strategy type
        super().__init__()
        self.strategy_type = CHAT_WITH_FABRIC

    async def create_agents(self, history, client_principal=None):

        conversation_summary = await self._summarize_conversation(history)

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

        execute_dax_query_tool = FunctionTool(
            execute_dax_query, description="Execute an DAX query and return the results."
        )     

        validate_sql_query_tool = FunctionTool(
            validate_sql_query, description="Validate the syntax of an SQL query."
        )     

        execute_sql_query_tool = FunctionTool(
            execute_sql_query, description="Execute an SQL query and return the results."
        )     

        # Agents

        ## Triage Agent
        triage_prompt = await self._read_prompt("triage_agent", {"conversation_summary": conversation_summary})
        triage_agent = AssistantAgent(
            name="triage_agent",
            system_message=triage_prompt,
            model_client=self._get_model_client(), 
            tools=[get_all_datasources_info_tool, get_today_date, get_time],
            reflect_on_tool_use=True
        )

        ## DAX Query Agent
        dax_query_prompt = await self._read_prompt("dax_query_agent", {"conversation_summary": conversation_summary})        
        dax_query_agent = AssistantAgent(
            name="dax_query_agent",
            system_message=dax_query_prompt,
            model_client=self._get_model_client(), 
            tools=[queries_retrieval_tool, get_all_tables_info_tool, get_schema_info_tool, execute_dax_query_tool, get_today_date, get_time],
            reflect_on_tool_use=True
        )

        # ## SQL Query Agent 
        # sql_query_prompt = await self._read_prompt("sql_query_agent", {"conversation_summary": conversation_summary})             
        # sql_query_agent = AssistantAgent(
        #     name="sql_query_agent",
        #     system_message=sql_query_prompt,
        #     model_client=self._get_model_client(), 
        #     tools=[get_all_tables_info_tool, get_schema_info_tool, queries_retrieval_tool, validate_sql_query_tool, execute_sql_query_tool, get_today_date, get_time],
        #     reflect_on_tool_use=True
        # )        

        ## Chat Closure Agent
        chat_closure_prompt = await self._read_prompt("chat_closure")
        chat_closure = AssistantAgent(
            name="chat_closure",
            system_message=chat_closure_prompt,
            model_client=self._get_model_client(response_format=ChatGroupResponse)
        )
        
        # Group Chat Configuration

        self.max_rounds = int(os.getenv('MAX_ROUNDS', 20))

        def custom_selector_func(messages):
            """
            Selects the next agent based on the source of the last message.
            
            Transition Rules:
               user -> Triage Agent
               Triage Agent -> None (SelectorGroupChat will handle transition)
            """
            last_msg = messages[-1]
            if last_msg.source == "user":
                return "triage_agent"
            else:
                return None
            
        self.selector_func = custom_selector_func

        # self.agents = [triage_agent, dax_query_agent, sql_query_agent, chat_closure]
        self.agents = [triage_agent, dax_query_agent, chat_closure]

        return self._get_agent_configuration()

