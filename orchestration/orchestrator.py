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

class Orchestrator:
    def __init__(self, conversation_id: str, client_principal: dict):
        self._setup_logging()
        self.client_principal = client_principal
        self.conversation_id = self._use_or_create_conversation_id(conversation_id)
        self.short_id = self.conversation_id[:8]
        self.cosmosdb = CosmosDBClient()
        self.conversations_container = os.environ.get('CONVERSATION_CONTAINER', 'conversations')
        self.storage_account = os.environ.get('AZURE_STORAGE_ACCOUNT', 'your_storage_account')
        self.documents_container = os.environ.get('AZURE_STORAGE_CONTAINER', 'documents')
        orchestration_strategy = os.getenv('AUTOGEN_ORCHESTRATION_STRATEGY', 'classic_rag').replace('-', '_')
        self.agent_strategy = AgentStrategyFactory.get_strategy(orchestration_strategy)

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

    async def _create_agents_with_strategy(self, history: list[dict]) -> list:
        logging.info(f"[orchestrator] {self.short_id} Creating agents using {self.agent_strategy.strategy_type} strategy.")
        return await self.agent_strategy.create_agents(history, self.client_principal)

    async def _initiate_group_chat(self, agent_configuration: dict, ask: str) -> dict:
        try:
            logging.info(f"[orchestrator] {self.short_id} Creating group chat via SelectorGroupChat.")

            # Run agent chat
            group_chat = SelectorGroupChat(
                participants=agent_configuration["agents"],
                model_client=agent_configuration["model_client"],
                termination_condition=agent_configuration["termination_condition"],
                selector_func=agent_configuration["selector_func"]
            )
            result = await group_chat.run(task=ask)

            # Get answer, thoughts and reasoning from last message
            reasoning = ""
            last_message = result.messages[-1].content if result.messages else '{"answer":"No answer provided."}'
            try:
                message_data = json.loads(last_message)
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

    def _setup_logging(self):
        logging.getLogger('azure').setLevel(logging.WARNING)
        logging.basicConfig(level=os.environ.get('LOGLEVEL', 'DEBUG').upper())

    def _use_or_create_conversation_id(self, conversation_id: str) -> str:
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            logging.info(f"[orchestrator] Creating new conversation_id. {conversation_id}")
        return conversation_id
