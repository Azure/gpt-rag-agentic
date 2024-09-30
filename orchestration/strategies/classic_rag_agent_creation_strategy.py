import logging

from autogen import UserProxyAgent, AssistantAgent, register_function
from tools import vector_index_retrieve

from .base_agent_creation_strategy import BaseAgentCreationStrategy
from ..constants import CLASSIC_RAG

class ClassicRAGAgentCreationStrategy(BaseAgentCreationStrategy):

    def __init__(self):
        super().__init__()
        self.strategy_type = CLASSIC_RAG


    @property
    def max_rounds(self):
        return 10 
    
    @property
    def send_introductions(self):
        return False
    

    def create_agents(self, llm_config, history):
        """
        Classic RAG creation strategy that creates the basic agents and registers functions.
        """
        
        user_proxy_prompt = self._read_prompt("user_proxy")
        user_proxy = UserProxyAgent(
            name="user", 
            system_message=user_proxy_prompt, 
            human_input_mode="NEVER",
            code_execution_config=False,
            is_termination_msg=lambda msg: msg.get("content") is not None and "TERMINATE" in msg["content"]
        )

        conversation_summary = self._summarize_conversation(history)
        assistant_prompt = self._read_prompt("classic_rag_assistant", {"conversation_summary": conversation_summary})
        assistant = AssistantAgent(
            name="assistant", 
            system_message=assistant_prompt, 
            human_input_mode="NEVER",
            llm_config=llm_config
        )

        # Register functions
        register_function(
            vector_index_retrieve,
            caller=assistant,
            executor=user_proxy,
            name="vector_index_retrieve", 
            description="Search the knowledge base for sources to ground and give context to answer a user question. Return sources.", 
        )

        return [user_proxy, assistant]