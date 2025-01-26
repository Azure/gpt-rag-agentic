from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from .nl2sql_base_agent_strategy import NL2SQLBaseStrategy
from ..constants import NL2SQL
from typing import Optional, List, Dict, Union
from pydantic import BaseModel
from .nl2sql_base_agent_strategy import (
    NL2SQLBaseStrategy,
    SchemaInfo,
    TablesList,
    ValidateSQLResult,
    ExecuteSQLResult
)
from tools import get_today_date, get_time

class NL2SQLStandardStrategy(NL2SQLBaseStrategy):

    def __init__(self):
        self.strategy_type = NL2SQL
        super().__init__()

    async def create_agents(self, llm_config, history, client_principal=None):
        """
        Creates agents and registers functions for the NL2SQL single agent scenario.
        """

        self.max_rounds = 20

        def get_schema_info(table_name: Optional[str] = None, column_name: Optional[str] = None) -> SchemaInfo:
            return self._get_schema_info(table_name, column_name)

        def get_all_tables_info() -> TablesList:
            return self._get_all_tables_info()

        def validate_sql_query(query: str) -> ValidateSQLResult:
            return self._validate_sql_query(query)     

        async def execute_sql_query(query: str) -> ExecuteSQLResult:
            return await self._execute_sql_query(query)

        # Create Assistant Agent
        conversation_summary = await self._summarize_conversation(history)
        assistant_prompt = await self._read_prompt("nl2sql_assistant", {"conversation_summary": conversation_summary})
        assistant = AssistantAgent(
            name="assistant",
            system_message=assistant_prompt,
            model_client=self._get_model_client(), 
            tools=[get_schema_info, validate_sql_query, get_all_tables_info, execute_sql_query, get_today_date, get_time],
            reflect_on_tool_use=True
        )

        # Create chat closure agent
        chat_closure_prompt = await self._read_prompt("chat_closure")
        chat_closure = AssistantAgent(
            name="chat_closure",
            system_message=chat_closure_prompt,
            model_client=self._get_model_client(),
            reflect_on_tool_use=True
        )

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