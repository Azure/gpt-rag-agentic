import base64
import json
import logging
import re
from typing import Annotated, Sequence
from urllib.parse import urlparse

from pydantic import BaseModel

from autogen_agentchat.agents import AssistantAgent, BaseChatAgent
from autogen_agentchat.base._chat_agent import Response
from autogen_agentchat.messages import (
    AgentEvent,
    ChatMessage,
    MultiModalMessage,
    TextMessage,
    ToolCallSummaryMessage,
)
from autogen_core import CancellationToken, Image
from autogen_core.model_context import BufferedChatCompletionContext
from autogen_core.tools import FunctionTool
from connectors import BlobClient
from tools import (
    get_time,
    get_today_date,
    multimodal_vector_index_retrieve,
)
from tools.ragindex.types import MultimodalVectorIndexRetrievalResult

from ..constants import Strategy
from .base_agent_strategy import BaseAgentStrategy

class MultimodalMessageCreator(BaseChatAgent):
    """
    A custom agent that constructs a MultiModalMessage from the vector_index_retrieve_wrapper 
    tool results. The actual tool call is done by another agent 
    (retrieval_agent) in the same SelectorGroupChat. 
    This agent simply scans the conversation for the tool's result, parses 
    text + image URLs, and returns a MultiModalMessage.
    """
    def __init__(self, name: str, system_prompt: str, model_context: BufferedChatCompletionContext):
        super().__init__(
            name=name,
            description="An agent that creates `MultiModalMessage` objects from the results of `vector_index_retrieve_wrapper`, executed by an `AssistantAgent` called `retrieval_agent`."
        )
        self._last_multimodal_result = None
        self.system_prompt = system_prompt + "\n\n"
        self._model_context = model_context

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
                    logging.warning(f"Failed to parse message content as JSON: {e}")
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
        image_captions = retrieval_data.get("captions", [])        
        image_captions = self.extract_image_caption_segments(image_captions)

        # Combine text snippets into a single string
        combined_text = self.system_prompt + "\n\n".join(texts) if texts else "No text results"

        # Fetch images from URLs
        image_objects = []
        max_images = 50  # maximum number of images to process (Azure OpenaI GPT-4o limit)
        image_count = 0
        url_list_pos = 0
        for url_list in image_urls:  # Assuming each item in image_urls is a list of URLs
            for url in url_list:  # Iterate through each URL in the sublist
                url_pos = 0
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

                    # Open the image using PIL
                    pil_img = Image.from_base64(base64_str)
                    
                    parsed_url = urlparse(url)
                    pil_img.path = parsed_url.path
                    pil_img.caption = image_captions[url_list_pos][url_pos] if url_list_pos < len(image_captions) and url_pos < len(image_captions[url_list_pos]) else None               

                    logging.debug(f"[multimodal_agent_strategy] Opened image from URL: {url}")
    
                    # Append the PIL Image object to your list (modify as needed)
                    image_objects.append(pil_img)
                    image_count += 1  # Increment the counter
                    logging.info(f"[multimodal_agent_strategy] Successfully loaded image from {url}")
                    url_pos += 1

                except Exception as e:
                    logging.error(f"[multimodal_agent_strategy] Could not load image from {url}: {e}")
            url_list_pos += 1


        # Construct and return the MultiModalMessage response
        multimodal_msg = MultiModalMessage(
            content=[combined_text, *image_objects],
            source=self.name
        )
        return Response(chat_message=multimodal_msg)

    def extract_image_caption_segments(self, image_captions):
        """
        Extracts caption segments from each string in image_captions.
        
        Each non-empty string in image_captions is expected to have one or more segments in the format:
        [<filename-with-figure-info.png>]: <caption text>
        
        This function splits each string into a list of such segments. Empty strings are returned unchanged.
        
        Parameters:
            image_captions (list of str): The list of caption strings to be processed.
            
        Returns:
            list: A list where each non-empty element is a list of extracted caption segments, and empty strings remain empty.
        """
        # Define the regex pattern:
        # - (\[[^]]+?\.png\]:.*?) matches a marker [ ...png]: followed by any text (non-greedy)
        # - (?=\[[^]]+?\.png\]:|$) is a lookahead to stop at the next marker or at the end of the string.
        pattern = r'(\[[^]]+?\.png\]:.*?)(?=\[[^]]+?\.png\]:|$)'
        
        new_image_captions = []
        for caption in image_captions:
            if caption.strip() == '':
                # Keep empty strings as they are.
                new_image_captions.append('')
            else:
                # Use DOTALL so that '.' matches newlines as well.
                segments = re.findall(pattern, caption, flags=re.DOTALL)
                new_image_captions.append(segments)
        
        return new_image_captions

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        """
        Reset the agent state if needed. 
        In this basic example, we clear the internal variable.
        """
        self._last_multimodal_result = None

class MultimodalAgentStrategy(BaseAgentStrategy):
    def __init__(self):
        super().__init__()
        self.strategy_type = Strategy.MULTIMODAL_RAG

    async def create_agents(self, history, client_principal=None, access_token=None, output_mode=None, output_format=None):
        """
        Multimodal RAG creation strategy that creates the basic agents and registers functions.
        
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

        async def vector_index_retrieve_wrapper(
            input: Annotated[str, "An optimized query string based on the user's ask and conversation history, when available"]
        ) -> MultimodalVectorIndexRetrievalResult:
            return await multimodal_vector_index_retrieve(input, self._generate_security_ids(client_principal))

        vector_index_retrieve_tool = FunctionTool(
            vector_index_retrieve_wrapper, name="vector_index_retrieve", description="Performs a vector search using Azure AI Search fetching text and related images get relevant sources for answering the user's query."
        )

        # Agents

        ## Triage Agent
        triage_prompt = await self._read_prompt("triage_agent")
        triage_agent = AssistantAgent(
            name="triage_agent",
            system_message=triage_prompt,
            model_client=self._get_model_client(), 
            tools=[vector_index_retrieve_tool],
            reflect_on_tool_use=False,
            model_context=shared_context
        )

        ## Multimodal Message Creator
        multimodal_rag_message_prompt = await self._read_prompt("multimodal_rag_message")
        multimodal_creator = MultimodalMessageCreator(name="multimodal_creator", system_prompt=multimodal_rag_message_prompt, model_context=shared_context)

        ## Assistant Agent
        main_assistant_prompt = await self._read_prompt("main_assistant")        
        main_assistant = AssistantAgent(
            name="main_assistant",
            system_message=main_assistant_prompt,
            model_client=self._get_model_client(),
            reflect_on_tool_use=True
        )
        
        ## Chat Closure Agent
        chat_closure = await self._create_chat_closure_agent(output_format, output_mode)

        # Agent Configuration

        # Optional: Override the termination condition for the assistant. Set None to disable each termination condition.
        # self.max_rounds = int(os.getenv('MAX_ROUNDS', 8))
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
                selected_agent = "triage_agent"
                logging.info(f"[multimodal_agent_strategy] selected {selected_agent} agent")
                return selected_agent
            if last_msg.source == "triage_agent" and isinstance(last_msg, ToolCallSummaryMessage):
                selected_agent = "multimodal_creator"
                logging.info(f"[multimodal_agent_strategy] selected {selected_agent} agent")
                return selected_agent                
            if last_msg.source == "multimodal_creator":
                selected_agent = "main_assistant"
                logging.info(f"[multimodal_agent_strategy] selected {selected_agent} agent")
                return selected_agent             
            if last_msg.source in ["main_assistant", "triage_agent"]:
                selected_agent = "chat_closure"
                logging.info(f"[multimodal_agent_strategy] selected {selected_agent} agent")
                return selected_agent                             
            selected_agent = "None"
            logging.info(f"[multimodal_agent_strategy] selected {selected_agent}")            
            return None
        
        self.selector_func = custom_selector_func

        self.agents = [triage_agent, multimodal_creator, main_assistant, chat_closure]
        
        return self._get_agents_configuration()
