import logging
import json
import os
import time
import uuid
from datetime import datetime
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

from tools import get_data_points_from_chat_log
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

    async def answer(self, ask: str) -> dict:
        start_time = time.time()
        conversation, history = await self._get_or_create_conversation()
        agent_configuration = await self._create_agents_with_strategy(history)
        answer_dict = await self._initiate_group_chat(agent_configuration, ask)
        response_time = time.time() - start_time
        await self._update_conversation_history(conversation, ask, answer_dict, response_time)
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

    async def _initiate_group_chat(self, agent_configuration: dict, ask: str) -> dict:
        
        answer_dict = {
            "conversation_id": self.conversation_id, 
            "answer": "",
            "thoughts": "",
            "data_points": []
        }

        try:
            logging.info(f"[orchestrator] {self.short_id} Creating group chat via SelectorGroupChat.")

            # 01. Create Group Chat            
            group_chat = SelectorGroupChat(
                participants=agent_configuration["agents"],
                model_client=agent_configuration["model_client"],
                termination_condition=agent_configuration["termination_condition"],
                selector_func=agent_configuration["selector_func"],
            )

            # 02. Run Group Chat            
            result = await group_chat.run(task=ask)
            final_answer = result.messages[-1].content if result.messages else "No answer generated."

            # 03. Format Output  
            # 03.01 Update data points from retrieval if available in chat log
            chat_log = self._get_chat_log(result.messages)
            answer_dict["data_points"] =  get_data_points_from_chat_log(chat_log)
            chat_log_formatted = self._print_chat_log(chat_log)
            logging.info(f"[orchestrator] {self.short_id} Chat log:\n{chat_log_formatted}")

            # 03.02 Remove termination message if present
            terminate_msg = agent_configuration.get('terminate_message', '')
            if terminate_msg and final_answer.endswith(terminate_msg):
                final_answer = final_answer[:-len(terminate_msg)].strip()  

            # 03.03 Update answer and thoughts
            # In some cases, the response may be a JSON, so we attempt to parse it to obtain 
            # the 'answer' and 'thoughts'. In other cases, the response is a simple string.
            try:
                parsed_json = json.loads(final_answer)
                if isinstance(parsed_json, dict):
                    answer_dict["answer"] = parsed_json.get("answer", parsed_json)
                    answer_dict["thoughts"] = parsed_json.get("thoughts", "")
            except json.JSONDecodeError:
                # final_answer is a plain string, keep it as-is
                answer_dict["answer"] = final_answer
                pass

            if answer_dict["thoughts"] == "":
                answer_dict["thoughts"] = chat_log_formatted

            return answer_dict

        except Exception as e:
            logging.error(f"[orchestrator] {self.short_id} An error occurred: {str(e)}", exc_info=True)
            answer_dict["answer"] =  f"We encountered an issue processing your request. Please try again later. Error {str(e)}"
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


    def _print_chat_log(self, chat_log):
        result = []
        max_length = 400
        ellipsis = "..."
        
        for item in chat_log:
            item_str = json.dumps(item, ensure_ascii=False)
            
            if len(item_str) > max_length:
                # Calculate the number of characters to keep from the start and end
                # Subtract the length of the ellipsis from max_length
                chars_to_keep = max_length - len(ellipsis)
                half_length = chars_to_keep // 2
                
                # In case of odd number, keep the extra character at the start
                start = item_str[:half_length + (chars_to_keep % 2)]
                end = item_str[-half_length:]
                truncated_str = f"{start}{ellipsis}{end}"
            else:
                truncated_str = item_str
            
            result.append(truncated_str + "\n")
        
        final_string = "".join(result)
        return final_string

    async def _update_conversation_history(self, conversation: dict, ask: str, answer_dict: dict, response_time: float):
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
