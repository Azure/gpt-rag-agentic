import logging

from autogen import UserProxyAgent, AssistantAgent, register_function
from tools import vector_index_retrieve, get_today_date, get_time
from typing_extensions import Annotated

from .base_agent_strategy import BaseAgentStrategy
from ..constants import CLASSIC_RAG

class ClassicRAGAgentStrategy(BaseAgentStrategy):

    def __init__(self):
        super().__init__()
        self.strategy_type = CLASSIC_RAG


    @property
    def max_rounds(self):
        return 10 
    
    @property
    def send_introductions(self):
        return False
    

    def create_agents(self, llm_config, history, client_principal=None):
        """
        Classic RAG creation strategy that creates the basic agents and registers functions.
        
        Parameters:
        - llm_config: Configuration for the large language model (LLM) used by the assistant agents.
        - history: The conversation history, which will be summarized to provide context for the assistant's responses.
        
        Returns:
        - agent_configuration: A dictionary that includes the list of agents and the allowed transitions between them.
        """

        # Create UserProxyAgent with a system message and termination condition
        user_proxy_prompt = self._read_prompt("user_proxy")
        user_proxy = UserProxyAgent(
            name="user", 
            system_message=user_proxy_prompt, 
            human_input_mode="NEVER",
            code_execution_config=False,
            is_termination_msg=lambda msg: msg.get("content") is not None and "TERMINATE" in msg["content"]
        )

        # Summarize conversation history and create AssistantAgent
        conversation_summary = self._summarize_conversation(history)
        assistant_prompt = self._read_prompt("classic_rag_assistant", {"conversation_summary": conversation_summary})
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

    
        # function closure for vector_index_retrieve
        def vector_index_retrieve_wrapper(
                  input: Annotated[str, "An optimized query string based on the user's ask and conversation history, when available"]
        ) -> Annotated[str, "The output is a string with the search results"]:
            return vector_index_retrieve(input, self._generate_security_ids(client_principal))

        register_function(
            vector_index_retrieve_wrapper,
            caller=assistant,
            executor=user_proxy,
            name="vector_index_retrieve_wrapper",
            description="Search the knowledge base for sources to ground and give context to answer a user question."
        )


        # Register functions
        register_function(
            vector_index_retrieve_wrapper,
            caller=assistant,
            executor=user_proxy,
            name="vector_index_retrieve", 
            description="Search the knowledge base for sources to ground and give context to answer a user question."
        )

        register_function(
            get_today_date,
            caller=assistant,
            executor=user_proxy,
            name="get_today_date",
            description="Provides today's date in YYYY-MM-DD format."
        )

        register_function(
            get_time,
            caller=assistant,
            executor=user_proxy,
            name="get_time",
            description="Provides the current time in HH:MM format."
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
