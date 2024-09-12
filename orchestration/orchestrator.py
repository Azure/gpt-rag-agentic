import io
import logging
import os
import sys
import time
from datetime import datetime
import autogen
import uuid
import warnings

from connectors import CosmosDBClient
from connectors import AzureOpenAIClient
from .agent_creation_strategy_factory import AgentCreationStrategyFactory

class Orchestrator:

    def __init__(self, conversation_id: str, client_principal: dict):
        self.setup_logging()
        self.client_principal = client_principal
        self.conversation_id = self.create_conversation_id(conversation_id)
        self.short_id = self.conversation_id[:8]
        self.cosmosdb = CosmosDBClient()
        self.conversations_container = os.environ.get('CONVERSATION_CONTAINER', 'conversations')
        self.aoai = AzureOpenAIClient()
        self.setup_llm_config()
        self.agent_creation_strategy = AgentCreationStrategyFactory.get_creation_strategy(
            os.getenv('AUTOGEN_ORCHESTRATION_STRATEGY', 'default')
        )
        self.max_rounds = int(os.environ.get('AUTOGEN_MAX_ROUNDS', 5))

    async def answer(self, ask: str) -> dict:
        """Process user query and generate a response from agents."""
        start_time = time.time()
        conversation, history = await self.get_or_create_conversation()
        conversation_summary = self.summarize_conversation(history)
        agents = self.create_agents(conversation_summary)
        answer_dict = await self.initiate_group_chat(agents, ask)
        await self.update_conversation(conversation, ask, answer_dict, time.time() - start_time)
        return answer_dict

    def setup_logging(self):
        """Configure logging for the orchestrator and Azure libraries."""
        logging.getLogger('azure').setLevel(logging.WARNING)
        logging.basicConfig(level=os.environ.get('LOGLEVEL', 'DEBUG').upper())

    def create_conversation_id(self, conversation_id: str) -> str:
        """Create a new conversation ID if none is provided."""
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            logging.info(f"[agentic_orchestrator] Creating new conversation_id. {conversation_id}")
            return conversation_id
        return conversation_id

    def setup_llm_config(self):
        """Set up the configuration for Azure OpenAI language model."""
        aoai_resource = os.environ.get('AZURE_OPENAI_RESOURCE', 'openai')
        self.llm_config = {
            "config_list": [
                {
                    "model": os.environ.get('AZURE_OPENAI_CHATGPT_DEPLOYMENT', 'openai-chatgpt'),
                    "base_url": f"https://{aoai_resource}.openai.azure.com",
                    "api_type": "azure",
                    "api_version": os.environ.get('AZURE_OPENAI_API_VERSION', '2024-02-01'),
                    "max_tokens": int(os.environ.get('AZURE_OPENAI_MAX_TOKENS', 1000)),
                    "azure_ad_token_provider": "DEFAULT"
                }
            ],
            "cache_seed": None  # Workaround for running in Azure Functions (read-only filesystem)
        }

    async def get_or_create_conversation(self) -> tuple:
        """Retrieve or create a conversation from CosmosDB."""
        conversation = await self.cosmosdb.get_document(self.conversations_container, self.conversation_id)
        if not conversation:
            conversation = await self.cosmosdb.create_document(self.conversations_container, self.conversation_id)
            logging.info(f"[agentic_orchestrator] {self.short_id} Created new conversation.")
        else:
            logging.info(f"[agentic_orchestrator] {self.short_id} Retrieved existing conversation.")
        return conversation, conversation.get('history', [])

    def summarize_conversation(self, history: list) -> str:
        """Summarize the conversation history."""
        if history:
            prompt = (
                "Summarize the conversation provided, identify its main points of discussion "
                f"and any conclusions that were reached. Conversation history: \n{history}"
            )
            conversation_summary = self.aoai.get_completion(prompt)
        else:
            conversation_summary = "The conversation just started."
        logging.info(f"[agentic_orchestrator] {self.short_id} Summary: {conversation_summary[:100]}")
        return conversation_summary

    def create_agents(self, conversation_summary: str) -> list:
        """Create agents based on the selected strategy."""
        logging.info(f"[agentic_orchestrator] {self.short_id} Creating agents using {self.agent_creation_strategy} strategy.")
        return self.agent_creation_strategy.create_agents(self.llm_config, conversation_summary)

    async def initiate_group_chat(self, agents: list, ask: str) -> dict:
        """Start the group chat and generate a response."""
        logging.info(f"[agentic_orchestrator] {self.short_id} Creating group chat.")
        groupchat = autogen.GroupChat(
            agents=agents, 
            messages=[],
            allow_repeat_speaker=False,
            max_round=self.max_rounds
        )

        logging.info(f"[agentic_orchestrator] {self.short_id} Creating group chat manager.")
        manager = autogen.GroupChatManager(
            groupchat=groupchat, 
            llm_config=self.llm_config
        )

        # Redirect stdout to capture chat execution output 
        captured_output = io.StringIO()
        sys.stdout = captured_output

        # Use warnings library to catch autogen UserWarning
        with warnings.catch_warnings(record=True) as w:

            logging.info(f"[agentic_orchestrator] {self.short_id} Initiating chat.")
            chat_result = agents[0].initiate_chat(manager, message=ask, summary_method="last_msg")

            # print and reset stdout to its default value
            logging.info(f"[agentic_orchestrator] {self.short_id} Group chat thought process: \n{captured_output.getvalue()}.")
            sys.stdout = sys.__stdout__

            logging.info(f"[agentic_orchestrator] {self.short_id} Generating answer dictionary.")
            answer_dict = {
                "conversation_id": self.conversation_id,
                "answer": "",
                "data_points": "",
                "thoughts": captured_output.getvalue()  # Optional: Capture thought process
            }
            if chat_result and chat_result.summary:
                answer_dict['answer'] = chat_result.summary
                if len(chat_result.chat_history) >= 2 and chat_result.chat_history[-2]['role'] == 'tool':
                    answer_dict['data_points'] = chat_result.chat_history[-2]['content']
            else:
                logging.info(f"[agentic_orchestrator] {self.short_id} No valid response generated.")
                # Check if there's a warning with content filtering block
                if len(w) > 0 and 'finish_reason=\'content_filter\'' in str(w[-1].message):
                    answer_dict['answer'] = "The content was blocked due to content filtering."

            return answer_dict

    async def update_conversation(self, conversation: dict, ask: str, answer_dict: dict, response_time: float):
        """Update conversation in the CosmosDB with the new interaction."""
        logging.info(f"[agentic_orchestrator] {self.short_id}Updating conversation.")
        history = conversation.get('history', [])
        history.append({"role": "user", "content": ask})
        history.append({"role": "assistant", "content": answer_dict['answer']})

        interaction = {
            'user_id': self.client_principal['id'],
            'user_name': self.client_principal['name'],
            'response_time': round(response_time, 2)
        }
        interaction.update(answer_dict)

        conversation_data = conversation.get('conversation_data', {'start_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'interactions': []})
        conversation_data['interactions'].append(interaction)

        conversation['conversation_data'] = conversation_data
        conversation['history'] = history
        await self.cosmosdb.update_document(self.conversations_container, conversation)
        logging.info(f"[agentic_orchestrator] {self.short_id}Finished updating conversation.")
