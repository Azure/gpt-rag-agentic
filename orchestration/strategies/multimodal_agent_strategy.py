from typing_extensions import Annotated, Dict, Any

from tools import get_time, get_today_date, multimodal_vector_index_retrieve
from .base_agent_strategy import BaseAgentStrategy
from ..constants import MULTIMODAL_RAG
from autogen_agentchat.agents import BaseChatAgent
from connectors import BlobClient

import requests, json
from io import BytesIO

import logging
import base64

import re
import logging
from typing import Sequence, Union, Annotated, Dict, Any
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base._chat_agent import Response
from autogen_agentchat.messages import TextMessage, MultiModalMessage, ToolCallExecutionEvent, ToolCallSummaryMessage
from autogen_agentchat.messages import AgentEvent, ChatMessage
from autogen_core import CancellationToken, Image  
import requests
from io import BytesIO

class MultimodalMessageCreator(BaseChatAgent):
    """
    A custom agent that constructs a MultiModalMessage from the vector_index_retrieve_wrapper 
    tool results. The actual tool call is done by another agent 
    (retrieval_agent) in the same SelectorGroupChat. 
    This agent simply scans the conversation for the tool's result, parses 
    text + image URLs, and returns a MultiModalMessage.
    """
    def __init__(self, name: str, multimodal_rag_message_prompt: str):
        super().__init__(
            name=name,
            description="An agent that creates `MultiModalMessage` objects from the results of `vector_index_retrieve_wrapper`, executed by an `AssistantAgent` called `retrieval_agent`."
        )
        # You can track internal state here if needed.
        self._last_multimodal_result = None
        self.multimodal_rag_message_prompt = multimodal_rag_message_prompt

    @property
    def produced_message_types(self):
        """
        Return the message types this agent can produce.
        We produce a MultiModalMessage.
        """
        return (MultiModalMessage,)

    async def on_messages(
        self, 
        messages: Sequence[ChatMessage], 
        cancellation_token: CancellationToken
    ) -> Response:
        """
        Handles incoming messages to process vector index retrieval results 
        and construct a MultiModalMessage response.
        """
        retrieval_data = None

        # Iterate through messages in reverse to find the latest relevant tool output
        for msg in reversed(messages):
            if isinstance(msg, ToolCallSummaryMessage):
                try:
                    msg_content = msg.content   
                    parsed_content = json.loads(msg_content)
                    if "texts" in parsed_content or "images" in parsed_content:
                        retrieval_data = parsed_content
                        break
                except json.JSONDecodeError as e:
                    print(f"Failed to parse message content as JSON: {e}")
                    continue

        if not retrieval_data:
            # Fallback response when no relevant data is found
            fallback_msg = TextMessage(
                content="No vector retrieval data was found in the conversation.",
                source=self.name
            )
            return Response(chat_message=fallback_msg)

        # Extract text and image data
        texts = retrieval_data.get("texts", [])
        image_urls = retrieval_data.get("images", [])

        # Combine text snippets into a single string
        combined_text = self.multimodal_rag_message_prompt + "\n\n".join(texts) if texts else "No text results"

        # Fetch images from URLs
        image_objects = []
        max_images = 50  # maximum number of images to process (Azure OpenaI GPT-4o limit)
        image_count = 0    
        for url_list in image_urls:  # Assuming each item in image_urls is a list of URLs
            for url in url_list:  # Iterate through each URL in the sublist
                if image_count >= max_images:
                    logging.info(f"[multimodal_agent_strategy] Reached the maximum image limit of {max_images}. Stopping further downloads.")
                    break  # Stop processing more URLs                
                try:

                    # Initialize BlobClient with the blob URL
                    blob_client = BlobClient(blob_url=url)
                    logging.debug(f"[multimodal_agent_strategy] Initialized BlobClient for URL: {url}")
                    
                    # Download the blob data as bytes
                    blob_data = blob_client.download_blob()
                    logging.debug(f"[multimodal_agent_strategy] Downloaded blob data for URL: {url}")
                    
                    # Open the image using PIL
                    base64_str = base64.b64encode(blob_data).decode('utf-8')
                    pil_img = Image.from_base64(base64_str)
                    logging.debug(f"[multimodal_agent_strategy] Opened image from URL: {url}")
                    
                    # Append the PIL Image object to your list (modify as needed)
                    image_objects.append(pil_img)
                    image_count += 1  # Increment the counter
                    logging.info(f"[multimodal_agent_strategy] Successfully loaded image from {url}")

                except Exception as e:
                    logging.error(f"[multimodal_agent_strategy] Could not load image from {url}: {e}")


        # Construct and return the MultiModalMessage response
        multimodal_msg = MultiModalMessage(
            content=[combined_text, *image_objects],
            source=self.name
        )
        return Response(chat_message=multimodal_msg)

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        """
        Reset the agent state if needed. 
        In this basic example, we clear the internal variable.
        """
        self._last_multimodal_result = None

class MultimodalAgentStrategy(BaseAgentStrategy):
    def __init__(self):
        super().__init__()
        self.strategy_type = MULTIMODAL_RAG

    async def create_agents(self, history, client_principal=None):
        """
        Multimodal RAG creation strategy that creates the basic agents and registers functions.
        
        Parameters:
        - history: The conversation history, which will be summarized to provide context for the assistant's responses.
        
        Returns:
        - agent_configuration: A dictionary that includes the agents team, default model client, termination conditions and selector function.

        Note:
        To use a different model for an specific agent, instantiate a separate AzureOpenAIChatCompletionClient and assign it instead of using self._get_model_client().
        """

        # Conversation Summary
        conversation_summary = await self._summarize_conversation(history)

        # Function closure for multimodal_vector_index_retrieve
        async def vector_index_retrieve_wrapper(
            input: Annotated[str, "An optimized query string based on the user's ask and conversation history, when available"]
        ) -> Annotated[Dict[str, Any], "The output includes separate lists of text and image URLs"]:
            return await multimodal_vector_index_retrieve(input, self._generate_security_ids(client_principal))
        
        # Retrieval Prompt
        triage_prompt = await self._read_prompt("triage_agent", {"conversation_summary": conversation_summary})
        triage_agent = AssistantAgent(
            name="triage_agent",
            system_message=triage_prompt,
            model_client=self._get_model_client(), 
            tools=[vector_index_retrieve_wrapper],
            reflect_on_tool_use=False
        )

        # Multimodal Message Creator
        multimodal_rag_message_prompt = await self._read_prompt("multimodal_rag_message", {"conversation_summary": conversation_summary})
        multimodal_creator = MultimodalMessageCreator("multimodal_creator", multimodal_rag_message_prompt)

        # Assistant Agent
        main_assistant = AssistantAgent(
            name="main_assistant",
            system_message="You are a helpful assistant who always includes the word ANSWERED at the end of your responses.",
            model_client=self._get_model_client(),
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

        def custom_selector_func(messages):
            """
            Selects the next agent based on the source of the last message.
            
            Transition Rules:
                user -> triage_agent
                triage_agent (ToolCallSummaryMessage) -> multimodal_creator
                multimodal_creator -> assistant
                Other -> None (SelectorGroupChat will handle transition)
            """            
            last_msg = messages[-1]
            if last_msg.source == "user":
                return "triage_agent"
            if last_msg.source == "triage_agent" and isinstance(last_msg, ToolCallSummaryMessage):
                return "multimodal_creator"
            if last_msg.source == "multimodal_creator":
                return "main_assistant" 
            if last_msg.source in ["main_assistant", "triage_agent"]:
                return "chat_closure"                 
            return None
        
        self.selector_func = custom_selector_func

        self.agents = [triage_agent, multimodal_creator, main_assistant, chat_closure]
        
        return self._get_agent_configuration()