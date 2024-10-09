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

from connectors import CosmosDBClient

from .agent_creation_strategy_factory import AgentCreationStrategyFactory

class Orchestrator:

    def __init__(self, conversation_id: str, client_principal: dict):
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
        self.orchestration_strategy = os.getenv('AUTOGEN_ORCHESTRATION_STRATEGY', 'classic_rag')
        if self.orchestration_strategy == 'classic-rag':
            self.orchestration_strategy = 'classic_rag'        
        
        # Agent creation strategy        
        self._setup_llm_config()
        self.agent_creation_strategy = AgentCreationStrategyFactory.get_creation_strategy(self.orchestration_strategy)
        self.max_rounds = self.agent_creation_strategy.max_rounds
        self.send_introductions=self.agent_creation_strategy.send_introductions

    ### Main functions

    async def answer(self, ask: str) -> dict:
        """Process user query and generate a response from agents."""
        start_time = time.time()
        conversation, history = await self._get_or_create_conversation()
        agent_configuration = self._create_agents_with_strategy(history)
        answer_dict = await self._initiate_group_chat(agent_configuration, ask)
        response_time = time.time() - start_time
        await self._update_conversation(conversation, ask, answer_dict, response_time)
        logging.info(f"[orchestrator] {self.short_id} Generated response in {response_time:.3f} sec.")       
        return answer_dict
    
    async def _get_or_create_conversation(self) -> tuple:
        """Retrieve or create a conversation from CosmosDB."""
        conversation = await self.cosmosdb.get_document(self.conversations_container, self.conversation_id)
        if not conversation:
            conversation = await self.cosmosdb.create_document(self.conversations_container, self.conversation_id)
            logging.info(f"[orchestrator] {self.short_id} Created new conversation.")
        else:
            logging.info(f"[orchestrator] {self.short_id} Retrieved existing conversation.")
        return conversation, conversation.get('history', [])
    
    def _create_agents_with_strategy(self, history: str) -> list:
        """Create agents based on the selected strategy."""
        logging.info(f"[orchestrator] {self.short_id} Creating agents using {self.agent_creation_strategy.strategy_type} strategy.")
        return self.agent_creation_strategy.create_agents(self.llm_config, history)

    async def _initiate_group_chat(self, agent_configuration: dict, ask: str) -> dict:
        """
        Initiates a group chat with multiple agents and generates a response based on the chat interactions.
        
        This method creates a group chat instance, manages it using the GroupChatManager, and captures 
        the chat's execution process, including the agents' thoughts and decisions. It logs various steps 
        and captures the chat process' output, returning a dictionary with the conversation details, 
        including the final answer, any data points, and the chat's thought process.

        Args:
            agent_configuration (dict): A dictionary that configures the group chat, containing:
                - "agents" (list): A list of agents who will participate in the conversation.
                - "transitions" (dict): Defines the allowed or disallowed speaker transitions between agents.
                - "transitions_type" (str): Specifies how transitions are managed, such as allowing or restricting 
                certain agents to speak based on predefined rules. (allowed or disallowed)
            ask (str): The initial message to start the group chat and guide the conversation.

        Returns:
            dict: A dictionary containing:
                - conversation_id (str): A unique identifier for the conversation.
                - answer (str): The final response generated from the chat.
                - data_points (str): Any extracted data points from the conversation.
                - thoughts (str): The captured thought process and output of the agents during the conversation.
        
        Logs:
            Logs various steps of the group chat initiation, including thought processes, warnings, 
            and potential issues such as content filtering blocks.

        Raises:
            None: This function does not raise any exceptions, but logs potential issues.

        Notes:
            - The captured thoughts and stdout redirection allow for insight into the decision-making 
            process of the agents.
            - If no valid response is generated or if content filtering occurs, this is handled by 
            providing an appropriate message in the `answer_dict`.
        """
        # Initialize captured_output and original_stdout before the try block
        captured_output = io.StringIO()
        original_stdout = sys.stdout

        try:
            logging.info(f"[orchestrator] {self.short_id} Creating group chat.")
            agents = agent_configuration["agents"]
            groupchat = autogen.GroupChat(
                agents=agents, 
                allowed_or_disallowed_speaker_transitions=agent_configuration["transitions"] ,
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

            # Redirect stdout to capture chat execution output 
            sys.stdout = captured_output

            # Use warnings library to catch autogen UserWarning
            with warnings.catch_warnings(record=True) as w:
                logging.info(f"[orchestrator] {self.short_id} Initiating chat.")
                chat_result = agents[0].initiate_chat(manager, message=ask, summary_method="last_msg")

                logging.info(f"[orchestrator] {self.short_id} Group chat thought process: \n{captured_output.getvalue()}.")

            logging.info(f"[orchestrator] {self.short_id} Generating answer dictionary.")
            answer_dict = {
                "conversation_id": self.conversation_id,
                "answer": "",
                "data_points": "",
                "thoughts": "Agents group chat:\n\n" + captured_output.getvalue()  # Optional: Capture thought process
            }

            if chat_result and chat_result.summary:
                # Check if there are at least two messages in the chat history and the second last message is from a tool
                if len(chat_result.chat_history) >= 2 and chat_result.chat_history[-2]['role'] == 'tool':
                    # Extract data points from the content of the second last message in the chat history
                    answer_dict['data_points'] = chat_result.chat_history[-2]['content']
                
                # Get the summary of the chat result and strip any leading/trailing whitespace
                chat_answer = chat_result.summary.strip()
                
                # If the chat answer ends with a specific marker (e.g., "\n\n****"), remove the marker and strip any trailing whitespace
                if chat_answer.endswith("\n\n****"):
                    chat_answer = chat_answer[:-6].strip()
                
                # Store the processed chat answer in the answer dictionary
                answer_dict['answer'] = chat_answer                
            else:
                logging.info(f"[orchestrator] {self.short_id} No valid response generated.")
                # Check if there's a warning with content filtering block
                if len(w) > 0 and 'finish_reason=\'content_filter\'' in str(w[-1].message):
                    answer_dict['answer'] = "The content was blocked due to content filtering."
                else:
                    answer_dict['answer'] = "We had a problem answering your question. Please try again in a few minutes."

            return answer_dict

        except AttributeError as ae:
            # Handle the specific AttributeError related to 'openai.error'
            captured_stdout = captured_output.getvalue()

            # Reset stdout to its original value
            sys.stdout = original_stdout

            logging.error(f"[orchestrator] {self.short_id} An AttributeError occurred: {str(ae)}", exc_info=True)
            logging.error(f"[orchestrator] {self.short_id} Captured stdout before error:\n{captured_stdout}")

            return {
                "conversation_id": self.conversation_id,
                "answer": "We encountered an issue processing your request. Please try again later.",
                "data_points": "",
                "thoughts": f"An error occurred while processing your request. Captured output before error:\n{captured_stdout}"
            }

        except openai.OpenAIError as oe:
            # This block will be reached if 'openai.error.OpenAIError' is replaced with 'openai.OpenAIError'
            captured_stdout = captured_output.getvalue()

            # Reset stdout to its original value
            sys.stdout = original_stdout

            logging.error(f"[orchestrator] {self.short_id} An OpenAI error occurred: {str(oe)}", exc_info=True)
            logging.error(f"[orchestrator] {self.short_id} Captured stdout before error:\n{captured_stdout}")

            return {
                "conversation_id": self.conversation_id,
                "answer": "We encountered an issue processing your request. Please try again later.",
                "data_points": "",
                "thoughts": f"An error occurred while processing your request. Captured output before error:\n{captured_stdout}"
            }

        except Exception as e:
            # Handle all other exceptions
            captured_stdout = captured_output.getvalue()

            # Reset stdout to its original value
            sys.stdout = original_stdout

            logging.error(f"[orchestrator] {self.short_id} An unexpected error occurred: {str(e)}", exc_info=True)
            logging.error(f"[orchestrator] {self.short_id} Captured stdout before error:\n{captured_stdout}")

            return {
                "conversation_id": self.conversation_id,
                "answer": "We had a problem answering your question. Please try again in a few minutes.",
                "data_points": "",
                "thoughts": f"An unexpected error occurred. Captured output before error:\n{captured_stdout}"
            }

        finally:
            # Ensure that stdout is always reset, even if an exception occurs
            sys.stdout = original_stdout

    async def _update_conversation(self, conversation: dict, ask: str, answer_dict: dict, response_time: float):
        """Update conversation in the CosmosDB with the new interaction."""
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

        conversation_data = conversation.get('conversation_data', {'start_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'interactions': []})
        conversation_data['interactions'].append(interaction)

        conversation['conversation_data'] = conversation_data
        conversation['history'] = history
        await self.cosmosdb.update_document(self.conversations_container, conversation)
        logging.info(f"[orchestrator] {self.short_id} Finished updating conversation.")

    ### Utility functions

    def _setup_logging(self):
        """Configure logging for the orchestrator and Azure libraries."""
        logging.getLogger('azure').setLevel(logging.WARNING)
        logging.basicConfig(level=os.environ.get('LOGLEVEL', 'DEBUG').upper())

    def _use_or_create_conversation_id(self, conversation_id: str) -> str:
        """Create a new conversation ID if none is provided."""
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            logging.info(f"[orchestrator] Creating new conversation_id. {conversation_id}")
            return conversation_id
        return conversation_id

    def _setup_llm_config(self):
        """Set up the configuration for Azure OpenAI language model."""
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
