import logging
import os
from autogen import UserProxyAgent, AssistantAgent, register_function
from .nl2sql_base_agent_strategy import NL2SQLBaseStrategy
from typing import Optional, List, Dict, Union
from pydantic import BaseModel
from tools import queries_retrieval, tables_retrieval, columns_retrieval
from .nl2sql_base_agent_strategy import (
    NL2SQLBaseStrategy,
    ValidateSQLResult,
    ExecuteSQLResult
)
from tools import get_today_date, get_time

class NL2SQLFewshotScaledStrategy(NL2SQLBaseStrategy):

    def __init__(self):
        self.strategy_type = "nl2sql_fewshot_scaled"
        super().__init__()

    @property
    def max_rounds(self):
        return 30

    @property
    def send_introductions(self):
        return False

    def create_agents(self, llm_config, history):
        """
        Creates agents and registers functions for the NL2SQL single agent scenario.
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
            system_message=assistant_prompt,
            human_input_mode="NEVER",
            llm_config=llm_config
        )

        # Create chat closure agent
        chat_closure_prompt = self._read_prompt("chat_closure")
        chat_closure = AssistantAgent(
            name="chat_closure", 
            system_message=chat_closure_prompt, 
            human_input_mode="NEVER",
            llm_config=llm_config
        )        

        def validate_sql_query(query: str) -> ValidateSQLResult:
            return self._validate_sql_query(query)

        @user_proxy.register_for_execution()
        @assistant.register_for_llm(description="Execute an SQL query and return the results as a list of dictionaries. Each dictionary represents a row.")
        async def execute_sql_query(query: str) -> ExecuteSQLResult:
            return await self._execute_sql_query(query)   
        # Register functions with assistant and user_proxy

        register_function(
            tables_retrieval,
            caller=assistant,
            executor=user_proxy,
            name="tables_retrieval", 
            description="Search for tables before the assistant generate a new query. Return tables and their descriptions.", 
        )

        register_function(
            columns_retrieval,
            caller=assistant,
            executor=user_proxy,
            name="columns_retrieval", 
            description="Search for tables columns before the assistant generate a new query. Return columns and their descriptions.", 
        )        

        register_function(
            validate_sql_query,
            caller=assistant,
            executor=user_proxy,
            name="validate_sql_query",
            description="Validate the syntax of an SQL query. Returns is_valid as True if valid, or is_valid as False with an error message if invalid."
        )

        register_function(
            queries_retrieval,
            caller=assistant,
            executor=user_proxy,
            name="queries_retrieval", 
            description="Search for similar queries before the assistant generate a new query. Return queries.", 
        )

        register_function(
            get_today_date,
            caller=assistant,
            executor=user_proxy,
            name="get_today_date",
            description="Provides today's date in the format YYYY-MM-DD."
        )

        register_function(
            get_time,
            caller=assistant,
            executor=user_proxy,
            name="get_time",
            description="Provides the current time in the format HH:MM."
        )

        # Define allowed transitions between agents
        allowed_transitions = {
            chat_closure: [user_proxy],
            user_proxy: [assistant],
            assistant: [chat_closure, user_proxy],
        }
        
        # Return agent configuration
        agent_configuration = {
            "agents": [user_proxy, assistant, chat_closure],
            "transitions": allowed_transitions,
            "transitions_type": "allowed"
        }

        return agent_configuration
