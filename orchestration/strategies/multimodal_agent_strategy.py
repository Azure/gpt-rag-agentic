# /orchestration/strategies/multimodal_agent_strategy.py
import logging
import json
from typing_extensions import Annotated
from autogen import UserProxyAgent, register_function
from autogen.agentchat.contrib.multimodal_conversable_agent import MultimodalConversableAgent

from ..constants import MULTIMODAL_RAG  # or define a new constant
from .base_agent_strategy import BaseAgentStrategy
from tools import multimodal_vector_index_retrieve, get_today_date, get_time

class MultimodalAgent(BaseAgentStrategy):
    def __init__(self):
        super().__init__()
        self.strategy_type =  MULTIMODAL_RAG

    @property
    def max_rounds(self):
        return 8

    @property
    def send_introductions(self):
        return False

    def create_agents(self, llm_config, history, client_principal=None):
        # 1. Create a user proxy
        user_proxy_prompt = self._read_prompt("user_proxy")  # or a custom prompt
        user_proxy = UserProxyAgent(
            name="user",
            system_message=user_proxy_prompt,
            human_input_mode="NEVER",
        )

        # 2. Summarize conversation (optional)
        conversation_summary = self._summarize_conversation(history)
        # 3. Create a MultimodalConversableAgent
        #    This agent can handle or embed images in the conversation.
        mm_agent_prompt = self._read_prompt("multimodal_rag_assistant", {"conversation_summary": conversation_summary})
        mm_agent = MultimodalConversableAgent(
            name="assistant",
            system_message=mm_agent_prompt,
            human_input_mode="NEVER",
            llm_config=llm_config,
        )

        # 4. Register functions
        def multimodal_vector_index_retrieve_wrapper(
              input: Annotated[str, "An optimized query string based on the user's ask and conversation history, when available."]
        ) -> Annotated[str, "The output is a string with the search results including text and images when available."]:
            return multimodal_vector_index_retrieve(input, self._generate_security_ids(client_principal))
        register_function(
            multimodal_vector_index_retrieve_wrapper,
            caller=mm_agent,
            executor=user_proxy,
            name="multimodal_vector_index_retrieve",
            description="Search the knowledge base to retrieve text and image source data to ground and give context to answer a user question"
        )

        register_function(
            get_today_date,
            caller=mm_agent,
            executor=user_proxy,
            name="get_today_date",
            description="Provides today's date in YYYY-MM-DD format."
        )

        register_function(
            get_time,
            caller=mm_agent,
            executor=user_proxy,
            name="get_time",
            description="Provides the current time in HH:MM format."
        )        

        # 5. Return agent configuration
        allowed_transitions = {
            mm_agent: [user_proxy],
            user_proxy: [mm_agent],
        }
        return {
            "agents": [user_proxy, mm_agent],
            "transitions": allowed_transitions,
            "transitions_type": "allowed"
        }
