import os
import re

from typing import List, Optional, Annotated
from pydantic import BaseModel
from autogen_agentchat.agents import AssistantAgent
from autogen_core.tools import FunctionTool
from autogen_agentchat.messages import TextMessage
from tools import ExecuteQueryResult

from .base_agent_strategy import BaseAgentStrategy
from ..constants import Strategy

from tools import (
    get_time,
    get_today_date,
    queries_retrieval,
    get_all_datasources_info,
    tables_retrieval,
    measures_retrieval,
    get_all_tables_info,
    get_schema_info,
    execute_dax_query,
    validate_sql_query,
    execute_sql_query,
)

## Agent Response Types

class ChatGroupResponse(BaseModel):
    answer: str
    reasoning: str

class ChatGroupTextOnlyResponse(BaseModel):
    answer: str

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
        self.strategy_type = Strategy.CHAT_WITH_FABRIC

    async def create_agents(self, history, client_principal=None, access_token=None, text_only=False, optimize_for_audio=False):
        
        # Response configuration
        self.text_only=text_only
        self.optimize_for_audio=optimize_for_audio    

        # Model Context
        shared_context = await self._get_model_context(history)  

        # Wrapper Functions for Tools

        tables_retrieval_tool = FunctionTool(
            tables_retrieval, description="Retrieve a all tables that are relevant to the user question."
        )        

        get_all_datasources_info_tool = FunctionTool(
            get_all_datasources_info, description="Retrieve a list of all datasources."
        )

        get_all_tables_info_tool = FunctionTool(
            get_all_tables_info, description="Retrieve a list of tables filtering by the given datasource."
        )

        get_schema_info_tool = FunctionTool(
            get_schema_info, description="Retrieve information about tables and columns from the data dictionary."
        )        

        measures_retrieval_tool = FunctionTool(
            measures_retrieval, description="Retrieve a list of measures filtering by the given datasource."
        )

        queries_retrieval_tool = FunctionTool(
            queries_retrieval, description="Retrieve QueriesRetrievalResult a list of similar QueryItem containing a question, the correspondent query and reasoning."
        )

        async def execute_dax_query_wrapper(
            datasource: Annotated[str, "Target datasource"], 
            query: Annotated[str, "DAX Query"]
        ) -> ExecuteQueryResult:
            return await execute_dax_query(datasource, query, access_token)

        execute_dax_query_tool = FunctionTool(
            execute_dax_query_wrapper, name="execute_dax_query", description="Execute a DAX query and return the results."
        )     

        validate_sql_query_tool = FunctionTool(
            validate_sql_query, description="Validate the syntax of an SQL query."
        )     

        execute_sql_query_tool = FunctionTool(
            execute_sql_query, description="Execute a SQL query against the datasource provided by the Triage Agent and return the results."
        )     

        # Agents      

        ## Triage Agent
        triage_prompt = await self._read_prompt("triage_agent")
        triage_agent = AssistantAgent(
            name="triage_agent",
            system_message=triage_prompt,
            model_client=self._get_model_client(), 
            tools=[get_all_datasources_info_tool, tables_retrieval_tool, get_today_date, get_time],
            reflect_on_tool_use=True,
            model_context=shared_context
        )
        
        ## DAX Query Agent
        dax_query_prompt = await self._read_prompt("dax_query_agent")        
        dax_query_agent = AssistantAgent(
            name="dax_query_agent",
            system_message=dax_query_prompt,
            model_client=self._get_model_client(), 
            tools=[queries_retrieval_tool, measures_retrieval_tool, get_schema_info_tool, execute_dax_query_tool, get_today_date, get_time],
            reflect_on_tool_use=True,
            model_context=shared_context
        )

        ## SQL Query Agent 
        sql_query_prompt = await self._read_prompt("sql_query_agent")             
        sql_query_agent = AssistantAgent(
            name="sql_query_agent",
            system_message=sql_query_prompt,
            model_client=self._get_model_client(), 
            tools=[queries_retrieval_tool, get_schema_info_tool, validate_sql_query_tool, execute_sql_query_tool, get_today_date, get_time],
            reflect_on_tool_use=True,
            model_context=shared_context
        )        

        # Society Of Mind Agent (Query Agents)
        # inner_termination = TextMentionTermination("QUESTION_ANSWERED")
        # response_prompt = "Copy the content of the last agent message exactly, without mentioning any of the intermediate discussion."
        # inner_team = RoundRobinGroupChat([dax_query_agent, sql_query_agent], termination_condition=inner_termination)
        # inner_team = SelectorGroupChat(
        #                 participants=[dax_query_agent, sql_query_agent],
        #                 model_client=self._get_model_client(),
        #                 termination_condition=inner_termination,
        #                 max_turns=30
        #             )
        # query_agents = SocietyOfMindAgent("query_agents", team=inner_team, response_prompt=response_prompt, model_client=self._get_model_client())

        ## Chat Closure Agent
        if optimize_for_audio:
            prompt_name = "chat_closure_audio"
            chat_group_response_type = ChatGroupTextOnlyResponse
        else:
            prompt_name = "chat_closure"
            chat_group_response_type = ChatGroupResponse
        chat_closure = AssistantAgent(
            name="chat_closure",
            system_message=await self._read_prompt(prompt_name),
            model_client=self._get_model_client(response_format=chat_group_response_type)
        )
        
        # Group Chat Configuration
        self.max_rounds = int(os.getenv('MAX_ROUNDS', 40))

        def custom_selector_func(messages):
            """
            Selects the next agent based on the last message.
            """
            last_msg = messages[-1]

            if last_msg.source == "user":
                return "triage_agent"

            if isinstance(last_msg, TextMessage) and re.search(r"QUESTION_ANSWERED\.?$", last_msg.content.strip()):
                return "chat_closure"

            def is_datasource_selected(source, keyword):
                return last_msg.source == "triage_agent" and \
                    "DATASOURCE_SELECTED" in last_msg.content.strip() and \
                    keyword in last_msg.content.strip()

            agent_mapping = {
                "sql_query_agent": "sql_endpoint",
                "dax_query_agent": "semantic_model"
            }

            for agent, keyword in agent_mapping.items():
                if last_msg.source == agent or is_datasource_selected(last_msg.source, keyword):
                    return agent

            return "triage_agent"


        self.selector_func = custom_selector_func

        self.agents = [triage_agent, dax_query_agent, sql_query_agent, chat_closure]
        # self.agents = [triage_agent, query_agents, chat_closure]

        return self._get_agents_configuration()