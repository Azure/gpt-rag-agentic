import logging
import os
import time
from datetime import datetime
import autogen
import uuid
import sys
import io
import warnings

from connectors import CosmosDBClient
from connectors import AzureOpenAIClient

from .agent_creation_strategy_factory import AgentCreationStrategyFactory

class Orchestrator():
    def __init__(self, conversation_id, client_principal):
        # Set logging level for Azure libraries
        logging.getLogger('azure').setLevel(logging.WARNING)
        logging.getLogger('azure.cosmos').setLevel(logging.WARNING)
        
        # Configure logging level
        log_level = os.environ.get('LOGLEVEL', 'DEBUG').upper()
        logging.basicConfig(level=log_level)

        self.client_principal = client_principal

        # Create conversation_id if not provided
        if conversation_id is None or conversation_id == "":
            self.conversation_id = str(uuid.uuid4())
            logging.info(f"[base_orchestrator] {conversation_id} conversation_id is Empty, creating new conversation_id.")
        else:
            self.conversation_id = conversation_id
        self.short_id = self.conversation_id[:8]
   
        # Set connections
        self.cosmosdb = CosmosDBClient()
        self.conversations_container = 'conversations'
        self.aoai = AzureOpenAIClient()

        # Set LLM config (for autogen agents)
        self.llm_config = self._get_llm_config()
  
        # Agentic configuration
        strategy_type = os.getenv('AUTOGEN_ORCHESTRATOR_STRATEGY', 'default')   
        self.agent_creation_strategy = AgentCreationStrategyFactory.get_creation_strategy(strategy_type)
        self.max_rounds = os.environ.get('AUTOGEN_MAX_ROUNDS', 5) 
        
    def _get_llm_config(self):
        aoai_resource = os.environ.get('AZURE_OPENAI_RESOURCE', 'openai')
        aoai_deployment = os.environ.get('AZURE_OPENAI_CHATGPT_DEPLOYMENT', 'openai-chatgpt')
        aoai_api_version = os.environ.get('AZURE_OPENAI_API_VERSION', '2024-02-01')      
        aoai_max_tokens = int(os.environ.get('AZURE_OPENAI_MAX_TOKENS', 1000))
        return {
            "config_list": [
                {
                    "model": aoai_deployment,
                    "base_url": f"https://{aoai_resource}.openai.azure.com",
                    "api_type": "azure",
                    "api_version": aoai_api_version,
                    "max_tokens": aoai_max_tokens,
                    "azure_ad_token_provider": "DEFAULT"
                }
            ]
        }

    async def answer(self, ask: str) -> dict:
        start_time = time.time()
        logging.info(f"[agentic_orchestrator] {self.short_id} starting conversation flow.")

        # 1) Get conversation from db
        conversation = await self.cosmosdb.get_document(self.conversations_container, self.conversation_id)
        if conversation is None:
            conversation = await self.cosmosdb.create_document(self.conversations_container, self.conversation_id)
            logging.info(f"[agentic_orchestrator] {self.short_id} conversation created in db.")
        else:
            logging.info(f"[agentic_orchestrator] {self.short_id} conversation retrieved from db.")
        history = conversation.get('history', [])

        # 2) Summarize conversation history
        if len(history) > 0:
            prompt = f"Summarize the conversation provided, identify its main points of discussion and any conclusions that were reached. Conversation history: \n{history}"
            conversation_summary = self.aoai.get_completion(prompt)
        else:
            conversation_summary = "The conversation just started."
        logging.info(f"[agentic_orchestrator] {self.short_id} summary: {conversation_summary[:100]}.")

        # 3) Create Agents and Register Functions using the selected strategy
        agents = self.agent_creation_strategy.create_agents(conversation_summary, self.llm_config)

        # 4) Create the group chat and its manager, then start the group chat
        
        groupchat = autogen.GroupChat(
            agents=agents, 
            messages=[],
            allow_repeat_speaker=False,
            max_round=self.max_rounds
        )
        
        manager = autogen.GroupChatManager(
            groupchat=groupchat, 
            llm_config=self.llm_config
        )
        
        # Redirect stdout to capture chat execution output 
        captured_output = io.StringIO()
        sys.stdout = captured_output

        # Use warnings library to catch autogen UserWarning
        with warnings.catch_warnings(record=True) as w:

            # 5) Initiate group chat      
            chat_result = agents[0].initiate_chat(
                manager, 
                message=ask,
                summary_method="last_msg"
            )
            
            # print and reset stdout to its default value
            logging.info(f"[agentic_orchestrator] {self.short_id} group chat thought process: \n{captured_output.getvalue()}.")
            sys.stdout = sys.__stdout__

            # 6) Generate answer dictionary containing the conversation ID, the actual answer, sources (data points) and the thought process.
            answer_dict = {
                "conversation_id": self.conversation_id,
                "answer": "",
                "data_points": "",
                "thoughts": captured_output.getvalue()
            }
            if chat_result and chat_result.summary:
                answer_dict['answer'] = chat_result.summary
                if len(chat_result.chat_history) >= 2 and chat_result.chat_history[-2]['role'] == 'tool':
                    answer_dict['data_points'] = chat_result.chat_history[-2]['content']
            else:
                logging.info(f"[agentic_orchestrator] {self.short_id} No valid response generated.")
                # Check if there's a warning and if it contains content filtering information
                if len(w) > 0 and 'finish_reason=\'content_filter\'' in str(w[-1].message):
                    answer_dict['answer'] = "The content was blocked due to content filtering."

            # 7) Update conversation in db
            history.append({"role": "user", "content": ask})        
            history.append({"role": "assistant", "content": answer_dict['answer']})
            response_time = round(time.time() - start_time, 2)
            interaction = {
                'user_id': self.client_principal['id'], 
                'user_name': self.client_principal['name'], 
                'response_time': response_time
            }
            interaction.update(answer_dict)
            conversation_data = conversation.get('conversation_data', {'start_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'interactions': []})
            conversation_data['interactions'].append(interaction)
            conversation['conversation_data'] = conversation_data
            conversation['history'] = history
            conversation = await self.cosmosdb.update_document(self.conversations_container, conversation)


            logging.info(f"[agentic_orchestrator] {self.short_id} finished conversation flow. {response_time} seconds.")         
            return answer_dict
