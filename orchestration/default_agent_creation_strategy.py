import logging

from autogen import UserProxyAgent, AssistantAgent, register_function
from tools import vector_index_retrieve

from .base_agent_creation_strategy import BaseAgentCreationStrategy

class DefaultAgentCreationStrategy(BaseAgentCreationStrategy):
    def create_agents(self, conversation_summary, llm_config):
        """
        Default creation strategy that creates the basic agents and registers functions.
        """
        logging.info(f"[default_agent_creation_strategy] {self.short_id} summary: {conversation_summary[:100]}.")

        user_proxy_prompt = self._read_prompt("user_proxy")
        logging.info(f"[default_agent_creation_strategy] {self.short_id} user_proxy_prompt: {user_proxy_prompt[:100]}.")

        user_proxy = UserProxyAgent(
            name="user", 
            system_message=user_proxy_prompt, 
            human_input_mode="NEVER",
            code_execution_config=False,
            is_termination_msg=lambda msg: msg.get("content") is not None and "TERMINATE" in msg["content"]
        )
        logging.info(f"[default_agent_creation_strategy] {self.short_id} UserProxyAgent created.")

        assistant_prompt = self._read_prompt("assistant", {"conversation_summary": conversation_summary})
        logging.info(f"[default_agent_creation_strategy] {self.short_id} assistant_prompt: {assistant_prompt[:100]}.")

        assistant = AssistantAgent(
            name="assistant", 
            system_message=assistant_prompt, 
            human_input_mode="NEVER",
            llm_config=llm_config
        )
        logging.info(f"[default_agent_creation_strategy] {self.short_id} AssistantAgent created.")

        # Register functions
        register_function(
            vector_index_retrieve,
            caller=assistant,
            executor=user_proxy,
            name="vector_index_retrieve", 
            description="Search the knowledge base for sources to ground and give context to answer a user question. Return sources.", 
        )
        logging.info(f"[default_agent_creation_strategy] {self.short_id} Function vector_index_retrieve registered.")

        return [user_proxy, assistant]

            