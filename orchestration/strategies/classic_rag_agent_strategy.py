from typing_extensions import Annotated
from pydantic import BaseModel

from autogen_agentchat.agents import AssistantAgent
from autogen_core.tools import FunctionTool

from tools import get_time, get_today_date
from tools import vector_index_retrieve
from tools.retrieval.types import VectorIndexRetrievalResult

from .base_agent_strategy import BaseAgentStrategy
from ..constants import CLASSIC_RAG

## Agent Response Types

class ChatGroupResponse(BaseModel):
    answer: str
    reasoning: str

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
        # Model Context
        shared_context = await self._get_model_context(history) 

        # Wrapper Functions for Tools

        ## function closure for vector_index_retrieve
        async def vector_index_retrieve_wrapper(
            input: Annotated[str, "An optimized query string based on the user's ask and conversation history, when available"]
        ) -> VectorIndexRetrievalResult:
            return await vector_index_retrieve(input, self._generate_security_ids(client_principal))

        vector_index_retrieve_tool = FunctionTool(
            vector_index_retrieve_wrapper, name="vector_index_retrieve", description="Performs a vector search using Azure AI Search to retrieve relevant sources for answering the user's query."
        )

        # Agents

        ## Main Assistant Agent
        assistant_prompt = await self._read_prompt("classic_rag_assistant")
        main_assistant = AssistantAgent(
            name="main_assistant",
            system_message=assistant_prompt,
            model_client=self._get_model_client(), 
            tools=[vector_index_retrieve_tool, get_today_date, get_time],
            reflect_on_tool_use=True,
            model_context=shared_context
        )

        ## Chat Closure Agent
        chat_closure_prompt = await self._read_prompt("chat_closure")
        chat_closure = AssistantAgent(
            name="chat_closure",
            system_message=chat_closure_prompt,
            model_client=self._get_model_client(response_format=ChatGroupResponse)
        )

        # Agent Configuration

        # Optional: Override the termination condition for the assistant. Set None to disable each termination condition.
        # self.max_rounds = int(os.getenv('MAX_ROUNDS', 8))
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
                return "main_assistant"
            else:
                return None     
        
        self.selector_func = custom_selector_func
        
        self.agents = [main_assistant, chat_closure]
        
        return self._get_agent_configuration()
