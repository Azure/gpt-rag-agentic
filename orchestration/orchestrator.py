import logging
import os
import re
import time
import uuid
from datetime import datetime

from autogen_agentchat.teams import SelectorGroupChat
from connectors import CosmosDBClient
from .agent_strategy_factory import AgentStrategyFactory

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

    async def answer(self, ask: str, include_metadata: bool = True) -> dict:
        start_time = time.time()
        conversation, history = await self._get_or_create_conversation()
        agent_configuration = await self._create_agents_with_strategy(history)
        answer_dict = await self._initiate_group_chat(agent_configuration, ask, include_metadata)
        response_time = time.time() - start_time
        await self._update_conversation(conversation, ask, answer_dict, response_time)
        logging.info(f"[orchestrator] {self.short_id} Generated response in {response_time:.3f} sec.")
        return answer_dict

    async def _get_or_create_conversation(self) -> tuple:
        conversation = await self.cosmosdb.get_document(self.conversations_container, self.conversation_id)
        if not conversation:
            conversation = await self.cosmosdb.create_document(self.conversations_container, self.conversation_id)
            logging.info(f"[orchestrator] {self.short_id} Created new conversation.")
        else:
            logging.info(f"[orchestrator] {self.short_id} Retrieved existing conversation.")
        return conversation, conversation.get('history', [])

    async def _create_agents_with_strategy(self, history: str) -> list:
        logging.info(f"[orchestrator] {self.short_id} Creating agents using {self.agent_strategy.strategy_type} strategy.")
        return await self.agent_strategy.create_agents(history, self.client_principal)

    async def _initiate_group_chat(self, agent_configuration: dict, ask: str, include_metadata: bool) -> dict:
        try:
            logging.info(f"[orchestrator] {self.short_id} Creating group chat via SelectorGroupChat.")
            group_chat = SelectorGroupChat(
                participants=agent_configuration["agents"],
                model_client=agent_configuration["model_client"],
                termination_condition=agent_configuration["termination_condition"],
                selector_func=agent_configuration["selector_func"],
            )
            result = await group_chat.run(task=ask)
            final_answer = result.messages[-1].content if result.messages else "No answer generated."
            if final_answer.endswith(agent_configuration['terminate_message']):
                final_answer = final_answer[:-len(agent_configuration['terminate_message'])].strip()
            answer_dict = {"conversation_id": self.conversation_id, "answer": final_answer}
            if include_metadata:
                chat_log = self._get_chat_log(result.messages)
                data_points = self._get_data_points(chat_log)
                answer_dict.update({"thoughts": chat_log, "data_points": data_points})
            return answer_dict
        except Exception as e:
            logging.error(f"[orchestrator] {self.short_id} An error occurred: {str(e)}", exc_info=True)
            answer_dict = {"conversation_id": self.conversation_id, "answer": f"We encountered an issue processing your request. Please try again later. Error {str(e)}"}
            if include_metadata:
                answer_dict.update({"thoughts": [], "data_points": []})
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

        for msg in chat_log:
            if msg["message_type"] == "ToolCallRequestEvent":
                content = msg["content"][0]
                call_id = content.split("id='")[1].split("',")[0]
                call_id_map[call_id] = None
            elif msg["message_type"] == "ToolCallExecutionEvent":
                content = msg["content"][0]
                call_id = content.split("call_id='")[1].split("')")[0]
                if call_id in call_id_map:

                    content_match = re.search(r"content='(.*?)',", content)
                    if content_match:
                        data = content_match.group(1)
                        entries = re.findall(pattern, data, re.DOTALL | re.IGNORECASE)
                        data_points.extend(entries)
                        
        return data_points

    async def _update_conversation(self, conversation: dict, ask: str, answer_dict: dict, response_time: float):
        logging.info(f"[orchestrator] {self.short_id} Updating conversation.")
        history = conversation.get('history', [])
        history.append({"role": "user", "content": ask})
        history.append({"role": "assistant", "content": answer_dict['answer']})
        interaction = {'user_id': self.client_principal['id'], 'user_name': self.client_principal['name'], 'response_time': round(response_time, 2)}
        interaction.update(answer_dict)
        conversation_data = conversation.get('conversation_data', {'start_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'interactions': []})
        conversation_data['interactions'].append(interaction)
        conversation['conversation_data'] = conversation_data
        conversation['history'] = history
        await self.cosmosdb.update_document(self.conversations_container, conversation)
        logging.info(f"[orchestrator] {self.short_id} Finished updating conversation.")

    def _setup_logging(self):
        logging.getLogger('azure').setLevel(logging.WARNING)
        logging.basicConfig(level=os.environ.get('LOGLEVEL', 'DEBUG').upper())

    def _use_or_create_conversation_id(self, conversation_id: str) -> str:
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            logging.info(f"[orchestrator] Creating new conversation_id. {conversation_id}")
        return conversation_id
