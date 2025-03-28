import json
import logging
import os
import re
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from .constants import Strategy, OutputFormat, OutputMode
from autogen_agentchat.teams import SelectorGroupChat
from connectors import CosmosDBClient
from .agent_strategy_factory import AgentStrategyFactory


# ---------- Configuration & Dependency Classes ----------

class OrchestratorConfig:
    def __init__(
        self,
        conversation_container: str = None,
        storage_account: str = None,
        orchestration_strategy: Strategy = None,
    ):
        self.conversation_container = conversation_container or os.environ.get('CONVERSATION_CONTAINER', 'conversations')
        self.storage_account = storage_account or os.environ.get('AZURE_STORAGE_ACCOUNT', 'your_storage_account')
        strategy_from_env = os.getenv('AUTOGEN_ORCHESTRATION_STRATEGY', 'classic_rag').replace('-', '_')
        self.orchestration_strategy = (orchestration_strategy or Strategy(strategy_from_env))


class ConversationManager:
    def __init__(self, cosmosdb_client: CosmosDBClient, config: OrchestratorConfig,
                 client_principal: dict, conversation_id: str):
        self.cosmosdb = cosmosdb_client
        self.config = config
        self.client_principal = client_principal
        self.conversation_id = self._use_or_create_conversation_id(conversation_id)
        self.short_id = self.conversation_id[:8]

    def _use_or_create_conversation_id(self, conversation_id: str) -> str:
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            logging.info(f"[orchestrator] Creating new conversation_id: {conversation_id}")
        return conversation_id

    async def get_or_create_conversation(self) -> dict:
        conversation = await self.cosmosdb.get_document(self.config.conversation_container, self.conversation_id)
        if not conversation:
            new_conversation = {
                "id": self.conversation_id,
                "start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "user_id": self.client_principal.get("id", "unknown") if self.client_principal else "unknown",
                "user_name": self.client_principal.get("name", "anonymous") if self.client_principal else "anonymous",
                "conversation_id": self.conversation_id,
                "history": []  # initialize an empty chat log
            }
            conversation = await self.cosmosdb.create_document(self.config.conversation_container, self.conversation_id, new_conversation)
            logging.info(f"[orchestrator] {self.short_id} Created new conversation.")
        else:
            logging.info(f"[orchestrator] {self.short_id} Retrieved existing conversation.")
        return conversation

    async def update_conversation(self, conversation: dict, ask: str, answer: str):
        logging.info(f"[orchestrator] {self.short_id} Updating conversation.")
        history = conversation.get("history", [])
        history.extend([
            {"speaker": "user", "content": ask},
            {"speaker": "assistant", "content": answer}
        ])
        simplified_conversation = {
            "id": self.conversation_id,
            "start_date": conversation.get("start_date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "user_id": self.client_principal.get("id", "unknown") if self.client_principal else "unknown",
            "user_name": self.client_principal.get("name", "anonymous") if self.client_principal else "anonymous",
            "conversation_id": self.conversation_id,
            "history": history
        }
        await self.cosmosdb.update_document(self.config.conversation_container, simplified_conversation)
        logging.info(f"[orchestrator] {self.short_id} Finished updating conversation.")


# ---------- Parsing Helpers ----------

class ChatLogParser:
    @staticmethod
    def get_chat_log(messages) -> list:
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
            chat_log.append({
                "speaker": msg.source,
                "message_type": msg.type,
                "content": safe_content
            })
        return chat_log

    @staticmethod
    def extract_data_points(chat_log) -> list:
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
                    logging.warning(f"[orchestrator] Error processing message: {e}.")
        else:
            logging.warning("[orchestrator] Chat log is empty or not provided.")
        return data_points


class MessageParser:
    @staticmethod
    def parse_message(message_str: str) -> dict:
        pattern = r"(\w+)=((?:'(?:\\'|[^'])*'|\"(?:\\\"|[^\"])*\"|\[[^\]]+\]|\([^\)]+\)|[^\s]+))"
        pairs = re.findall(pattern, message_str)
        result = {}
        for key, value in pairs:
            if (value.startswith("'") and value.endswith("'")) or (value.startswith("\"") and value.endswith("\"")):
                value = value[1:-1]
            result[key] = value
        if 'models_usage' in result and result['models_usage'].startswith('RequestUsage'):
            start_index = message_str.find('models_usage=')
            if start_index != -1:
                usage_str = message_str[start_index:].split(' ', 1)[1]
                usage_match = re.match(r"RequestUsage\((.*?)\)", usage_str)
                if usage_match:
                    result['models_usage'] = usage_match.group(1)
        return result


# ---------- Orchestrators ----------

class BaseOrchestrator(ABC):
    def __init__(
        self,
        conversation_id: str,
        config: OrchestratorConfig,
        client_principal: dict = None,
        access_token: str = None,
        agent_strategy=None
    ):
        self.client_principal = client_principal
        self.access_token = access_token
        self.cosmosdb =  CosmosDBClient()
        self.conversation_manager = ConversationManager(self.cosmosdb, config, client_principal, conversation_id)
        self.conversation_id = self.conversation_manager.conversation_id
        self.short_id = self.conversation_id[:8]
        self.config = config

        # Agent strategy is injected if provided; otherwise, use the factory.
        if agent_strategy:
            self.agent_strategy = agent_strategy
        else:
            strategy_key = config.orchestration_strategy
            self.agent_strategy = AgentStrategyFactory.get_strategy(strategy_key)

    @abstractmethod
    async def answer(self, ask: str):
        pass

    @abstractmethod
    async def _create_agents_with_strategy(self, history: list[dict]) -> dict:
        pass

    async def _update_conversation(self, conversation: dict, ask: str, answer: str):
        await self.conversation_manager.update_conversation(conversation, ask, answer)


class RequestResponseOrchestrator(BaseOrchestrator):
    async def answer(self, ask: str) -> dict:
        start_time = time.time()
        conversation = await self.conversation_manager.get_or_create_conversation()
        history = conversation.get("history", [])
        agent_configuration = await self._create_agents_with_strategy(history)
        answer_dict = await self._initiate_group_chat(agent_configuration, ask)
        await self._update_conversation(conversation, ask, answer_dict['answer'])
        response_time = time.time() - start_time
        logging.info(f"[orchestrator] {self.short_id} Generated response in {response_time:.3f} sec.")
        return answer_dict

    async def _initiate_group_chat(self, agent_configuration: dict, ask: str) -> dict:
        try:
            logging.info(f"[orchestrator] {self.short_id} Creating group chat via SelectorGroupChat.")
            group_chat = SelectorGroupChat(
                participants=agent_configuration["agents"],
                model_client=agent_configuration["model_client"],
                termination_condition=agent_configuration["termination_condition"],
                selector_func=agent_configuration["selector_func"],
            )
            result = await group_chat.run(task=ask)

            # Parse the last message for answer and reasoning.
            reasoning = ""
            last_message = result.messages[-1].content if result.messages else '{"answer":"No answer provided."}'
            try:
                if isinstance(last_message, list):
                    message_data = last_message
                elif isinstance(last_message, (str, bytes, bytearray)):
                    message_data = json.loads(last_message)
                else:
                    raise TypeError(f"Unexpected message type: {type(last_message)}")
                answer = message_data.get("answer", "Oops! The agent team did not generate a response for the user.")
                reasoning = message_data.get("reasoning", "")
            except json.JSONDecodeError:
                answer = "Oops! The agent team did not generate a response for the user."
                logging.warning(f"[orchestrator] {self.short_id} Error: Malformed JSON. Using default values for answer and reasoning.")

            if answer.endswith(agent_configuration['terminate_message']):
                answer = answer[:-len(agent_configuration['terminate_message'])].strip()

            chat_log = ChatLogParser.get_chat_log(result.messages)
            data_points = ChatLogParser.extract_data_points(chat_log)

            answer_dict = {
                "conversation_id": self.conversation_id,
                "answer": answer,
                "reasoning": reasoning,
                "thoughts": chat_log,
                "data_points": data_points
            }
            return answer_dict

        except Exception as e:
            logging.error(f"[orchestrator] {self.short_id} An error occurred: {str(e)}", exc_info=True)
            return {
                "conversation_id": self.conversation_id,
                "answer": f"We encountered an issue processing your request. Please try again later. Error: {str(e)}",
                "reasoning": "",
                "thoughts": [],
                "data_points": []
            }

    async def _create_agents_with_strategy(self, history: list[dict]) -> dict:
        logging.info(f"[orchestrator] {self.short_id} Creating agents using {self.agent_strategy.strategy_type} strategy.")
        return await self.agent_strategy.create_agents(history, self.client_principal, self.access_token, OutputMode.REQUEST_RESPONSE, OutputFormat.JSON)


class StreamingOrchestrator(BaseOrchestrator):
    def __init__(
        self,
        conversation_id: str,
        config: OrchestratorConfig,
        client_principal: dict = None,
        access_token: str = None,
        agent_strategy=None
    ):
        super().__init__(conversation_id, config, client_principal, access_token, agent_strategy)
        self.optimize_for_audio = False

    def set_optimize_for_audio(self, optimize_for_audio: bool):
        self.optimize_for_audio = optimize_for_audio

    async def answer(self, ask: str):
        conversation = await self.conversation_manager.get_or_create_conversation()
        history = conversation.get("history", [])
        agent_config = await self._create_agents_with_strategy(history)
        group_chat = SelectorGroupChat(
            participants=agent_config["agents"],
            model_client=agent_config["model_client"],
            termination_condition=agent_config["termination_condition"],
            selector_func=agent_config["selector_func"],
        )
        stream = group_chat.run_stream(task=ask)
        streamed_conversation_id = False
        final_answer = ""
        try:
            async for response in stream:
                msg_str = str(response)
                try:
                    msg = MessageParser.parse_message(msg_str)
                except Exception as e:
                    logging.debug(f"Exception while parsing message: {e}")
                    continue
                msg_type = msg.get("type", "")
                msg_content = msg.get("content", "")
                if msg_type == 'ModelClientStreamingChunkEvent':
                    # stream conversation_id in the first chunk
                    if not streamed_conversation_id:
                        yield f"{conversation['id']} "
                        streamed_conversation_id = True

                    yield msg_content
                    # logging.info(f"Yielding chunk: {msg_content}")
                    final_answer += msg_content
        except Exception as error:
            logging.error(f"Error in streaming response: {error}", exc_info=True)
            error_message = f"\nWe encountered an issue processing your request. Please contact our support team for assistance. \n\n *{error}*"
            yield error_message
            final_answer += error_message

        await self._update_conversation(conversation, ask, final_answer)

    async def _create_agents_with_strategy(self, history: list[dict]) -> dict:
        output_format = OutputFormat.TEXT_TTS if self.optimize_for_audio else OutputFormat.TEXT
        logging.info(f"[orchestrator] {self.short_id} Creating agents using {self.agent_strategy.strategy_type} strategy. In Streaming mode and {output_format} output format.")        
        return await self.agent_strategy.create_agents(history, self.client_principal, self.access_token, OutputMode.STREAMING, output_format)
