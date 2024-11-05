import io
import logging
import openai
import os
import sys
import time
from datetime import datetime
import autogen
import uuid
import warnings
import json
import contextlib

from connectors import CosmosDBClient
from .agent_creation_strategy_factory import AgentCreationStrategyFactory

class Orchestrator:
    """
    The Orchestrator class manages interactions between the user and agents,
    handling conversations, agent creation, and coordinating responses based on
    the selected orchestration strategy. It interfaces with the LLM configuration,
    conversation storage, and group chat management.
    """

    def __init__(self, conversation_id: str, client_principal: dict):
        """
        Initialize the Orchestrator instance.

        Args:
            conversation_id (str): The unique identifier for the conversation.
                If not provided, a new one will be generated.
            client_principal (dict): The client principal containing user identification details.
        """
        self._setup_logging()

        # Get input parameters
        self.client_principal = client_principal
        self.conversation_id = self._use_or_create_conversation_id(conversation_id)
        self.short_id = self.conversation_id[:8]

        # Initialize connectors
        self.cosmosdb = CosmosDBClient()

        # Get environment variables
        self.conversations_container = os.environ.get('CONVERSATION_CONTAINER', 'conversations')
        self.aoai_resource = os.environ.get('AZURE_OPENAI_RESOURCE', 'openai')
        self.model = os.environ.get('AZURE_OPENAI_CHATGPT_DEPLOYMENT', 'openai-chatgpt')
        self.api_version = os.environ.get('AZURE_OPENAI_API_VERSION', '2024-02-01')
        self.max_tokens = int(os.environ.get('AZURE_OPENAI_MAX_TOKENS', 1000))

        # Normalize orchestration strategy
        self.orchestration_strategy = os.getenv('AUTOGEN_ORCHESTRATION_STRATEGY', 'classic_rag').replace('-', '_')

        # Agent creation strategy
        self._setup_llm_config()
        self.agent_creation_strategy = AgentCreationStrategyFactory.get_creation_strategy(self.orchestration_strategy)
        self.max_rounds = self.agent_creation_strategy.max_rounds
        self.send_introductions = self.agent_creation_strategy.send_introductions

    ### Main functions

    async def answer(self, ask: str) -> dict:
        """
        Process user query and generate a response from agents.

        Args:
            ask (str): The user's query.

        Returns:
            dict: A dictionary containing the conversation ID and the generated answer.
        """
        start_time = time.time()
        conversation, history = await self._get_or_create_conversation()
        agent_configuration = self._create_agents_with_strategy(history)
        answer_dict = await self._initiate_group_chat(agent_configuration, ask)
        response_time = time.time() - start_time
        await self._update_conversation(conversation, ask, answer_dict, response_time)
        logging.info(f"[orchestrator] {self.short_id} Generated response in {response_time:.3f} sec.")
        return answer_dict

    async def _get_or_create_conversation(self) -> tuple:
        """
        Retrieve or create a conversation from CosmosDB.

        Returns:
            tuple: A tuple containing the conversation document and its history.
        """
        conversation = await self.cosmosdb.get_document(self.conversations_container, self.conversation_id)
        if not conversation:
            conversation = await self.cosmosdb.create_document(self.conversations_container, self.conversation_id)
            logging.info(f"[orchestrator] {self.short_id} Created new conversation.")
        else:
            logging.info(f"[orchestrator] {self.short_id} Retrieved existing conversation.")
        return conversation, conversation.get('history', [])

    def _create_agents_with_strategy(self, history: str) -> list:
        """
        Create agents based on the selected strategy.

        Args:
            history (str): The conversation history.

        Returns:
            list: A list of agent configurations.
        """
        logging.info(f"[orchestrator] {self.short_id} Creating agents using {self.agent_creation_strategy.strategy_type} strategy.")
        return self.agent_creation_strategy.create_agents(self.llm_config, history)

    async def _initiate_group_chat(self, agent_configuration: dict, ask: str) -> dict:
        """
        Initiate a group chat with multiple agents and generate a response based on chat interactions.

        Args:
            agent_configuration (dict): Configuration for the group chat, including agents and transition rules.
            ask (str): The initial message to start the group chat.

        Returns:
            dict: A dictionary containing the conversation details, including the final answer and thought process.
        """
        try:
            logging.info(f"[orchestrator] {self.short_id} Creating group chat.")
            agents = agent_configuration["agents"]
            groupchat = autogen.GroupChat(
                agents=agents,
                allowed_or_disallowed_speaker_transitions=agent_configuration["transitions"],
                speaker_transitions_type=agent_configuration["transitions_type"],
                messages=[],
                max_round=self.max_rounds,
                send_introductions=self.send_introductions
            )

            logging.info(f"[orchestrator] {self.short_id} Creating group chat manager.")
            manager = autogen.GroupChatManager(
                groupchat=groupchat,
                llm_config=self.llm_config
            )

            # Capture the chat execution output
            with io.StringIO() as captured_output, contextlib.redirect_stdout(captured_output):
                with warnings.catch_warnings(record=True) as wrngs:
                    logging.info(f"[orchestrator] {self.short_id} Initiating chat.")
                    chat_result = await agents[0].a_initiate_chat(manager, message=ask, summary_method="last_msg")
                    # chat_result = agents[0].initiate_chat(manager, message=ask, summary_method="last_msg")

                thought_process = captured_output.getvalue()
                logging.info(f"[orchestrator] {self.short_id} Group chat thought process: \n{thought_process}.")

            logging.info(f"[orchestrator] {self.short_id} Generating answer dictionary.")
            answer_dict = self._generate_answer_dict(chat_result, thought_process, wrngs)
            return answer_dict

        except Exception as e:
            # Handle all exceptions
            logging.error(f"[orchestrator] {self.short_id} An error occurred: {str(e)}", exc_info=True)
            return {
                "conversation_id": self.conversation_id,
                "answer": "We encountered an issue processing your request. Please try again later.",
                "data_points": "",
                "reasoning": "",
                "sql_query": "",
                "thoughts": f"An error occurred while processing your request. Error details: {str(e)}"
            }

    async def _update_conversation(self, conversation: dict, ask: str, answer_dict: dict, response_time: float):
        """
        Update conversation in the CosmosDB with the new interaction.

        Args:
            conversation (dict): The conversation document from the database.
            ask (str): The user's query.
            answer_dict (dict): The generated answer and related information.
            response_time (float): The time taken to generate the response.
        """
        logging.info(f"[orchestrator] {self.short_id} Updating conversation.")
        history = conversation.get('history', [])
        history.append({"role": "user", "content": ask})
        history.append({"role": "assistant", "content": answer_dict['answer']})

        interaction = {
            'user_id': self.client_principal['id'],
            'user_name': self.client_principal['name'],
            'response_time': round(response_time, 2)
        }
        interaction.update(answer_dict)

        conversation_data = conversation.get(
            'conversation_data',
            {'start_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'interactions': []}
        )
        conversation_data['interactions'].append(interaction)

        conversation['conversation_data'] = conversation_data
        conversation['history'] = history
        await self.cosmosdb.update_document(self.conversations_container, conversation)
        logging.info(f"[orchestrator] {self.short_id} Finished updating conversation.")

    ### Utility functions

    def _setup_logging(self):
        """
        Configure logging for the orchestrator and Azure libraries.
        """
        logging.getLogger('azure').setLevel(logging.WARNING)
        logging.basicConfig(level=os.environ.get('LOGLEVEL', 'DEBUG').upper())

    def _use_or_create_conversation_id(self, conversation_id: str) -> str:
        """
        Create a new conversation ID if none is provided.

        Args:
            conversation_id (str): The provided conversation ID.

        Returns:
            str: The conversation ID to use.
        """
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            logging.info(f"[orchestrator] Creating new conversation_id. {conversation_id}")
        return conversation_id

    def _setup_llm_config(self):
        """
        Set up the configuration for Azure OpenAI language model.
        """
        self.llm_config = {
            "config_list": [
                {
                    "model": self.model,
                    "base_url": f"https://{self.aoai_resource}.openai.azure.com",
                    "api_type": "azure",
                    "api_version": self.api_version,
                    "max_tokens": self.max_tokens,
                    "azure_ad_token_provider": "DEFAULT"
                }
            ],
            "cache_seed": None  # Workaround for running in Azure Functions (read-only filesystem)
        }

    def _generate_answer_dict(self, chat_result: dict, thought_process: str, wrngs: list) -> dict:
        """
        Generate a dictionary containing the answer and related information based on the chat result.

        Args:
            chat_result (dict): The result from the chat, containing summary and chat history.
            thought_process (str): The captured thought process from the chat execution.
            wrngs (list): A list of warnings captured during the chat execution.

        Returns:
            dict: A dictionary with the conversation ID, answer, data points, reasoning, SQL query, and thoughts.
        """
        # Initialize the answer dictionary with default empty values
        answer_dict = {
            "conversation_id": self.conversation_id,
            "answer": "",
            "data_points": "",
            "reasoning": "",
            "sql_query": "",
            "thoughts": "Agents group chat:\n\n" + thought_process  # Optional: Capture thought process
        }

        # Check if chat_result and its summary are present
        if chat_result and chat_result.summary:

            # Get and clean the summary text
            chat_answer = chat_result.summary.strip()

            # Remove specific marker if present at the end of the summary
            marker = "\n\n****"
            if chat_answer.endswith(marker):
                chat_answer = chat_answer[:-len(marker)].strip()

            # Attempt to parse the summary as JSON
            try:
                # Check for code block formatting and remove backticks if present
                if chat_answer.startswith("```") and chat_answer.endswith("```"):
                    lines = chat_answer.strip('`').split('\n')
                    json_str = '\n'.join(lines).strip('json')                   
                else:
                    json_str = chat_answer

                # Parse the JSON string
                data = json.loads(json_str)

                # Extract fields with default empty strings if keys are missing
                answer_dict['answer'] = data.get("answer", "").strip()
                answer_dict['reasoning'] = data.get("reasoning", "").strip()
                answer_dict['sql_query'] = data.get("sql_query", "").strip()
                answer_dict['data_points'] = data.get("data_points", [])             

            except json.JSONDecodeError:
                # If parsing fails, treat the summary as a plain text answer
                answer_dict['answer'] = chat_answer

        else:
            # Log that no valid response was generated
            logging.info(f"[orchestrator] {self.short_id} No valid response generated.")
            # Handle content filtering warnings
            if wrngs and any('finish_reason=\'content_filter\'' in str(warning.message) for warning in wrngs):
                answer_dict['answer'] = "The content was blocked due to content filtering."
            else:
                answer_dict['answer'] = "We had a problem answering your question. Please try again in a few minutes."

        return answer_dict
