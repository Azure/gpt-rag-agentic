import json
import logging
import os
import re
import time
import uuid
from datetime import datetime

from autogen_agentchat.teams import SelectorGroupChat
from connectors import CosmosDBClient
from .agent_strategy_factory import AgentStrategyFactory

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

"""
Orchestrator Class

The `Orchestrator` class manages conversations using different agent strategies, supporting:

1. **Non-Streaming**: Returns the final response as a dictionary after processing the input.
2. **Streaming**: Streams intermediate responses as dictionaries and the final response when complete.
3. **Streaming (Text-Only)**: Streams only the final response as plain text without intermediate messages.

Initialization:
    Orchestrator(conversation_id: str, client_principal: dict = None, access_token: str = None)
        - conversation_id (str): Unique identifier for the conversation.
        - client_principal (dict, optional): User information including `id` and `name`.
        - access_token (str, optional): Token used for authentication.

Methods:
    async answer(self, ask: str) -> dict
        Generates a response using the selected agent strategy.
        Args:
            ask (str): User's question or prompt.
        Returns:
            dict: Final response with the following keys:
                - `conversation_id (str)`: The unique ID of the conversation.
                - `answer (str)`: The generated response.
                - `reasoning (str)`: The reasoning or thought process leading to the answer.
                - `thoughts (list[dict])`: Intermediate messages exchanged during the conversation.
                - `data_points (list[str])`: Extracted data references from tools or documents.

    async answer_stream(self, ask: str, text_only: bool = False)
        Streams responses as they are generated.
        Args:
            ask (str): User's question or prompt.
            text_only (bool, optional): If True, only the final answer is streamed as plain text. Default is False.
        Yields:
            - When `text_only=False`:
                dict: Intermediate and final responses with:
                    - `source (str)`: The message source (e.g., "assistant", "tool").
                    - `message_type (str)`: The type of message (e.g., "TextMessage").
                    - `models_usage (str)`: Information about model usage.
                    - `content (str)`: The message content.
                    - `final_answer (str)`: "true" for the final message, otherwise "false".
            - When `text_only=True`:
                str: The final answer as plain text, prefixed by the conversation ID.

Differences between Approaches:

- **Non-Streaming:** Provides the entire response at once after processing.
- **Streaming:** Delivers messages progressively, allowing real-time feedback.
- **Streaming (Text-Only):** Outputs only the final response, suitable for minimal output needs.
"""

class Orchestrator:
    def __init__(self, conversation_id: str, client_principal: dict = None, access_token: str = None):
        self._setup_logging()
        self.client_principal = client_principal
        self.access_token = access_token
        self.conversation_id = self._use_or_create_conversation_id(conversation_id)
        self.short_id = self.conversation_id[:8]
        self.cosmosdb = CosmosDBClient()
        self.optimize_for_audio = False
        self.conversations_container = os.environ.get('CONVERSATION_CONTAINER', 'conversations')
        self.storage_account = os.environ.get('AZURE_STORAGE_ACCOUNT', 'your_storage_account')
        self.documents_container = os.environ.get('AZURE_STORAGE_CONTAINER', 'documents')
        orchestration_strategy = os.getenv('AUTOGEN_ORCHESTRATION_STRATEGY', 'classic_rag').replace('-', '_')
        self.agent_strategy = AgentStrategyFactory.get_strategy(orchestration_strategy)

    ###########################################################################
    ## Non-Streaming API
    ###########################################################################

    async def answer(self, ask: str) -> dict:
        start_time = time.time()

        # Get existing conversation or create a new one
        conversation = await self._get_or_create_conversation()
        history = conversation.get("history", [])
        
        # Create agents and initiate group chat
        agent_configuration = await self._create_agents_with_strategy(history)
        answer_dict = await self._initiate_group_chat(agent_configuration, ask)

        # Update conversation with new chat log
        await self._update_conversation(conversation, ask, answer_dict['answer'])
        
        response_time = time.time() - start_time
        logging.info(f"[orchestrator] {self.short_id} Generated response in {response_time:.3f} sec.")
        return answer_dict

    async def _initiate_group_chat(self, agent_configuration: dict, ask: str) -> dict:
        try:
            logging.info(f"[orchestrator] {self.short_id} Creating group chat via SelectorGroupChat.")

            # Run agent chat
            group_chat = SelectorGroupChat(
                participants=agent_configuration["agents"],
                model_client=agent_configuration["model_client"],
                termination_condition=agent_configuration["termination_condition"],
                selector_func=agent_configuration["selector_func"],
            )
            result = await group_chat.run(task=ask)

            # Get answer, thoughts and reasoning from last message
            reasoning = ""
            last_message = result.messages[-1].content if result.messages else '{"answer":"No answer provided."}'
            try:
                if isinstance(last_message, list):
                    message_data = last_message
                elif isinstance(last_message, (str, bytes, bytearray)):
                    message_data = json.loads(last_message)
                else:
                    raise TypeError("Expected last_message to be str, bytes, or list, got: " + str(type(last_message)))
                answer = message_data.get("answer", "Oops! The agent team did not generate a response for the user.")
                reasoning = message_data.get("reasoning", "")
            except json.JSONDecodeError:
                answer = "Oops! The agent team did not generate a response for the user."
                logging.warning(f"[orchestrator] {self.short_id} Error: Malformed JSON. Using default values for answer and thoughts")

            if answer.endswith(agent_configuration['terminate_message']):
                answer = answer[:-len(agent_configuration['terminate_message'])].strip()
            
            # Get data points from chat log
            chat_log = self._get_chat_log(result.messages)
            data_points = self._get_data_points(chat_log)
            
            answer_dict = {"conversation_id": self.conversation_id, 
                           "answer": answer,
                           "reasoning": reasoning,                                   
                           "thoughts": chat_log,                   
                           "data_points": data_points}

            return answer_dict

        except Exception as e:
            logging.error(f"[orchestrator] {self.short_id} An error occurred: {str(e)}", exc_info=True)
            answer_dict = {"conversation_id": self.conversation_id, 
                           "answer": f"We encountered an issue processing your request. Please try again later. Error {str(e)}",
                           "reasoning": "", 
                           "thoughts": [], 
                           "data_points": []}
            return answer_dict  


    ###########################################################################
    ## Streaming API
    ###########################################################################

    async def answer_stream(self, ask: str, text_only: bool = False):
        """
        Streaming version of answer() using the group chat's run_stream method.
        
        In text_only mode:
        - Only the final answer (with termination keyword removed and formatting cleaned)
            is yielded as plain text with the conversation_id prepended.
        Otherwise:
        - Intermediate messages are yielded as dictionaries, with content truncated when needed.
        
        Finally, the conversation is updated with only the final answer text.
        """
        MAX_CONTENT_SIZE = 500
        self.optimize_for_audio = text_only
        conversation = await self._get_or_create_conversation()
        history = conversation.get("history", [])
        agent_config = await self._create_agents_with_strategy(history)
        terminate_keyword = agent_config.get("terminate_message", "TERMINATE")

        group_chat = SelectorGroupChat(
            participants=agent_config["agents"],
            model_client=agent_config["model_client"],
            termination_condition=agent_config["termination_condition"],
            selector_func=agent_config["selector_func"],
        )
        stream = group_chat.run_stream(task=ask)
        final_answer = ""

        async for response in stream:
            msg_str = str(response)
            if "TaskResult(" in msg_str:
                continue

            try:
                msg = self._parse_message(msg_str)
            except Exception:
                continue

            # Skip messages from the user.
            if msg.get("source", "") == "user":
                continue

            msg_type = msg.get("type", "")
            if msg_type == "ToolCallRequestEvent":
                # Yield tool events if not in text_only mode.
                for output in self._handle_tool_event(msg, text_only):
                    yield output

            elif msg_type == "TextMessage":
                should_break, final_text, outputs = self._handle_text_message(
                    msg, text_only, terminate_keyword, MAX_CONTENT_SIZE
                )
                if final_text:
                    final_answer = final_text
                for output in outputs:
                    yield output
                if should_break:
                    break

            else:
                continue

        # Update the conversation with the final answer.
        await self._update_conversation(conversation, ask, final_answer)

    def _parse_message(self, message_str: str) -> dict:
        """
        Extract key/value pairs from a message string.
        Expected format: key='value' or key=value (with some handling for nested parentheses/brackets).
        """
        pattern = r"(\w+)=((?:'(?:\\'|[^'])*'|\"(?:\\\"|[^\"])*\"|\[[^\]]+\]|\([^\)]+\)|[^\s]+))"
        pairs = re.findall(pattern, message_str)
        result = {}

        for key, value in pairs:
            if (value.startswith("'") and value.endswith("'")) or (value.startswith("\"") and value.endswith("\"")):
                value = value[1:-1]  # Remove surrounding quotes.
            result[key] = value

        # Handle cases where models_usage might be split.
        if 'models_usage' in result and result['models_usage'].startswith('RequestUsage'):
            start_index = message_str.find('models_usage=')
            if start_index != -1:
                usage_str = message_str[start_index:].split(' ', 1)[1]
                usage_match = re.match(r"RequestUsage\((.*?)\)", usage_str)
                if usage_match:
                    result['models_usage'] = usage_match.group(1)

        return result

    def _handle_tool_event(self, msg: dict, text_only: bool):
        """
        Process a ToolCallRequestEvent message.
        Yields a single dictionary output unless text_only mode is enabled.
        """
        if text_only:
            return

        models_usage = msg.get("models_usage", "")
        fn_name = msg.get("name", "")
        fn_arguments = msg.get("arguments", "")
        content = msg.get("content", "")
        output = {
            'conversation_id': self.conversation_id, 
            'source': msg.get("source", ""),
            'message_type': msg.get("type", ""),
            'models_usage': models_usage,
            'name': fn_name,
            'arguments': fn_arguments,
            'final_answer': "false",
            'content': f"Calling {fn_name}" if fn_name else content,
        }
        yield output

    def _handle_text_message(self, msg: dict, text_only: bool, terminate_keyword: str, max_content_size: int):
        """
        Process a TextMessage. Returns a tuple:
            (should_break, final_text, outputs)
        where:
        - should_break: True if this was the final message and streaming should stop.
        - final_text: The final answer text (if any).
        - outputs: A list of outputs to yield.
        """
        raw_content = msg.get("content", "")
        is_final = terminate_keyword in raw_content
        content = raw_content

        if is_final:
            content = content.replace(terminate_keyword, "").strip()
        elif len(content) > max_content_size:
            content = content[:max_content_size]

        outputs = []
        final_text = ""
        should_break = False

        def sanitize_json_string(content: str) -> str:
            content = content.strip()
            content = content.replace("\\\'", "'")
            content = content.replace("\\\\", "\\")
            if content.startswith("'") and content.endswith("'"):
                content = content.replace("'", '"')
            content = re.sub(r'\\[^\\"/bfnrtu]', '', content)
            return content

        if text_only:
            if is_final:
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    sanitized_content = sanitize_json_string(content)
                    data = json.loads(sanitized_content)
                except Exception:
                    data = {}
                answer_text = data.get("answer", "")
                answer_text = self._clean_answer_text(answer_text)
                final_text = answer_text
                outputs.append(f"{self.conversation_id} {answer_text}")
                should_break = True
            # In text_only mode, intermediate messages are not yielded.
        else:
            answer_text = content.decode("utf-8") if isinstance(content, bytes) else content
            outputs.append({
                'conversation_id': self.conversation_id, 
                'source': msg.get("source", ""),
                'message_type': msg.get("type", ""),
                'models_usage': msg.get("models_usage", ""),
                'name': "",
                'arguments': "",
                'final_answer': "true" if is_final else "false",
                'content': answer_text
            })
            if is_final:
                final_text = answer_text

        return should_break, final_text, outputs

    def _clean_answer_text(self, text: str) -> str:
        text = re.sub(r'\[.*?\]', '', text)             # Remove all text between square brackets.
        text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)  # Remove markdown links.
        text = re.sub(r'#+', '', text)                  # Remove markdown headers.
        text = re.sub(r'[_*`]', '', text)               # Remove formatting characters.
        text = re.sub(r'\s+', ' ', text).strip()        # Collapse whitespace.
        return text

    ###########################################################################
    ## Common
    ###########################################################################

    def _setup_logging(self):
        logging.getLogger('azure').setLevel(logging.WARNING)
        logging.basicConfig(level=os.environ.get('LOGLEVEL', 'DEBUG').upper())

    def _use_or_create_conversation_id(self, conversation_id: str) -> str:
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            logging.info(f"[orchestrator] Creating new conversation_id. {conversation_id}")
        return conversation_id

    async def _get_or_create_conversation(self) -> dict:
        conversation = await self.cosmosdb.get_document(self.conversations_container, self.conversation_id)
        if not conversation:
            new_conversation = {
                "id": self.conversation_id,
                "start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "user_id": self.client_principal.get("id", "unknown"),
                "user_name": self.client_principal.get("name", "anonymous"),
                "conversation_id": self.conversation_id,
                "history": []  # initialize an empty shared chat log
            }
            conversation = await self.cosmosdb.create_document(self.conversations_container, self.conversation_id, new_conversation)
            logging.info(f"[orchestrator] {self.short_id} Created new conversation.")
        else:
            logging.info(f"[orchestrator] {self.short_id} Retrieved existing conversation.")
        return conversation

    async def _update_conversation(self, conversation: dict, ask: str, answer: str):
        logging.info(f"[orchestrator] {self.short_id} Updating conversation.")
        # Retrieve the existing chat_log (if any) and extend it.
        history = conversation.get("history", [])
        history.extend([{"speaker": "user", "content": ask},{"speaker": "assistant", "content": answer}])
        # Create the simplified conversation document.
        simplified_conversation = {
            "id": self.conversation_id,
            "start_date": conversation.get("start_date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "user_id": self.client_principal.get("id", "unknown"),
            "user_name": self.client_principal.get("name", "anonymous"),
            "conversation_id": self.conversation_id,
            "history": history
        }
        await self.cosmosdb.update_document(self.conversations_container, simplified_conversation)
        logging.info(f"[orchestrator] {self.short_id} Finished updating conversation.")


    async def _create_agents_with_strategy(self, history: list[dict]) -> list:
        logging.info(f"[orchestrator] {self.short_id} Creating agents using {self.agent_strategy.strategy_type} strategy.")
        return await self.agent_strategy.create_agents(history, self.client_principal, self.access_token, self.optimize_for_audio)

    def _get_chat_log(self, messages):
        def make_serializable(obj):
            if isinstance(obj, (list, tuple)):
                return [make_serializable(item) for item in obj]
            elif isinstance(obj, dict):
                return {key: make_serializable(value) for key, value in obj.items()}
            elif isinstance(obj, str):
                return obj
            else:
                return repr(obj)

        chat_log = []
        for msg in messages:
            safe_content = make_serializable(msg.content)
            chat_log.append({"speaker": msg.source, "message_type": msg.type, "content": safe_content})
        return chat_log

    def _get_data_points(self, chat_log):
        data_points = []
        call_id_map = {}
        allowed_extensions = {'vtt', 'xlsx', 'xls', 'pdf', 'png', 'jpeg', 'jpg', 'bmp', 'tiff', 'docx', 'pptx'}
        extension_pattern = "|".join(allowed_extensions)
        pattern = rf'[\w\-.]+\.(?:{extension_pattern}): .*?(?=(?:[\w\-.]+\.(?:{extension_pattern})\:)|$)'
        if chat_log: 
            for msg in chat_log:
                try:
                    if "message_type" in msg and "content" in msg and isinstance(msg["content"], list) and msg["content"]:
                        if msg["message_type"] == "ToolCallRequestEvent":
                            content = msg["content"][0]
                            if "id='" in content:
                                call_id = content.split("id='")[1].split("',")[0]
                                call_id_map[call_id] = None
                        elif msg["message_type"] == "ToolCallExecutionEvent":
                            content = msg["content"][0]
                            if "call_id='" in content:
                                call_id = content.split("call_id='")[1].split("')")[0]
                                if call_id in call_id_map:
                                    if "content='" in content:
                                        data = content.split("content='")[1].rsplit("',", 1)[0]
                                        entries = re.findall(pattern, data, re.DOTALL | re.IGNORECASE)
                                        data_points.extend(entries)
                except Exception as e:
                    logging.warning(f"[orchestrator] {self.short_id} Error processing message: {e}.")
        else:
            logging.warning(f"[orchestrator] {self.short_id} Chat log is empty or not provided.")
        return data_points