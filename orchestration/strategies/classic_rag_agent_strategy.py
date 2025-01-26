from typing_extensions import Annotated

from tools import get_time, get_today_date, vector_index_retrieve
from .base_agent_strategy import BaseAgentStrategy
from ..constants import CLASSIC_RAG
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
        
class ClassicRAGAgentStrategy(BaseAgentStrategy):

    def __init__(self):
        super().__init__()
        self.strategy_type = CLASSIC_RAG

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

        # function closure for vector_index_retrieve
        async def vector_index_retrieve_wrapper(
            input: Annotated[str, "An optimized query string based on the user's ask and conversation history, when available"]
        ) -> Annotated[str, "The output is a string with the search results"]:
            return await vector_index_retrieve(input, self._generate_security_ids(client_principal))

        conversation_summary = await self._summarize_conversation(history)
        assistant_prompt = await self._read_prompt("classic_rag_assistant", {"conversation_summary": conversation_summary})
        main_assistant = AssistantAgent(
            name="main_assistant",
            system_message=assistant_prompt,
            model_client=self._get_model_client(), 
            tools=[vector_index_retrieve_wrapper, get_today_date, get_time],
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

        # Optional: Override the termination condition for the assistant. Set None to disable each termination condition.
        # self.max_rounds = 8
        # self.terminate_message = "TERMINATE"

        # Optional: Define a selector function to determine which agent to use based on the user's ask.
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
        
        self.agents = [main_assistant, chat_closure]
        
        return self._get_agent_configuration()
