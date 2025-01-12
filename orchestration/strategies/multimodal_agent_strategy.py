from typing_extensions import Annotated

from tools import get_time, get_today_date, multimodal_vector_index_retrieve
from .base_agent_strategy import BaseAgentStrategy
from ..constants import MULTIMODAL_RAG
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent

class MultimodalAgent(BaseAgentStrategy):
    def __init__(self):
        super().__init__()
        self.strategy_type =  MULTIMODAL_RAG

    async def create_agents(self, history, client_principal=None):
        """
        Classic RAG creation strategy that creates the basic agents and registers functions.
        
        Parameters:
        - history: The conversation history, which will be summarized to provide context for the assistant's responses.
        
        Returns:
        - agent_configuration: A dictionary that includes the agents team, default model client, termination conditions and selector function.

        Note:
        To use a different model for an specific agent, instantiate a separate AzureOpenAIChatCompletionClient and assign it instead of using self._get_model_client().
        """

        # function closure for multimodal_vector_index_retrieve
        async def vector_index_retrieve_wrapper(
            input: Annotated[str, "An optimized query string based on the user's ask and conversation history, when available"]
        ) -> Annotated[str, "The output is a string with the search results including text and images when available"]:
            return await multimodal_vector_index_retrieve(input, self._generate_security_ids(client_principal))

        conversation_summary = await self._summarize_conversation(history)
        assistant_prompt = await self._read_prompt("multimodal_rag_assistant", {"conversation_summary": conversation_summary})
        assistant = AssistantAgent(
            name="assistant",
            system_message=assistant_prompt,
            model_client=self._get_model_client(), 
            tools=[vector_index_retrieve_wrapper, get_today_date, get_time],
            reflect_on_tool_use=True
        )

        # Creating a UserProxyAgent since at least two participants are required for SelectorGroupChat.
        user_proxy = UserProxyAgent("user_proxy")

        # Optional: Override the termination condition for the assistant. Set None to disable each termination condition.
        # self.max_rounds = 8
        # self.terminate_message = "TERMINATE"

        # Optional: Define a selector function to determine which agent to use based on the user's ask.
        # self.selector_func = None
        
        self.agents = [assistant, user_proxy]
        
        return self._get_agent_configuration()

