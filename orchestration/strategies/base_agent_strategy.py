import logging
import os
import re

from connectors import AzureOpenAIClient
from azure.identity import ManagedIdentityCredential, AzureCliCredential, ChainedTokenCredential, get_bearer_token_provider
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_core.model_context import BufferedChatCompletionContext
from autogen_core.models import SystemMessage
from pydantic import BaseModel
from ..constants import OutputFormat, OutputMode
from autogen_agentchat.agents import AssistantAgent

# Agent response types
class ChatGroupResponse(BaseModel):
    answer: str
    reasoning: str

class BaseAgentStrategy:
    def __init__(self):
        # Azure OpenAI model client configuration
        self.aoai_resource = os.environ.get('AZURE_OPENAI_RESOURCE', 'openai')
        self.chat_deployment = os.environ.get('AZURE_OPENAI_CHATGPT_DEPLOYMENT', 'chat')
        self.model = os.environ.get('AZURE_OPENAI_CHATGPT_MODEL', 'gpt-4o')
        self.api_version = os.environ.get('AZURE_OPENAI_API_VERSION', '2024-10-21')
        self.max_tokens = int(os.environ.get('AZURE_OPENAI_MAX_TOKENS', 1000))
        self.temperature = float(os.environ.get('AZURE_OPENAI_TEMPERATURE', 0.7))

        # Autogen agent configuration (base to be overridden)
        self.agents = []
        self.terminate_message = "TERMINATE"
        self.max_rounds = int(os.getenv('MAX_ROUNDS', 8))
        self.selector_func = None
        self.context_buffer_size = int(os.getenv('CONTEXT_BUFFER_SIZE', 30))
        self.text_only=False 
        self.optimize_for_audio=False

    async def create_agents(self, history, client_principal=None, access_token=None, text_only=False, optimize_for_audio=False): 
        """
        Create agent instances for the strategy.

        This method must be implemented by subclasses to define how agents
        are created and configured for a given strategy.

        Parameters:
            history (list): The conversation history up to the current point.
            client_principal (dict, optional): Information about the client principal, such as group memberships.

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        raise NotImplementedError("This method should be overridden in subclasses.")

    def _get_agents_configuration(self):
        """
        Retrieve the configuration for agents managed by this strategy.

        Returns:
            dict: A dictionary containing the model client, agents, termination condition,
            and selector function.
        """
        return {
            "model_client": self._get_model_client(),
            "agents": self.agents,
            "terminate_message": self._get_terminate_message(),            
            "termination_condition": self._get_termination_condition(),
            "selector_func": self.selector_func
        }

    def _get_terminate_message(self):
        return self.terminate_message

    def _get_model_client(self, response_format=None):
        """
        Set up the configuration for the Azure OpenAI language model client.

        Initializes the `AzureOpenAIChatCompletionClient` with the required settings for
        interaction with Azure OpenAI services.
        """
        token_provider = get_bearer_token_provider(
            ChainedTokenCredential(
                ManagedIdentityCredential(),
                AzureCliCredential()
            ), "https://cognitiveservices.azure.com/.default"
        )
        return AzureOpenAIChatCompletionClient(
            azure_deployment=self.chat_deployment,
            model=self.model,
            azure_endpoint=f"https://{self.aoai_resource}.openai.azure.com",
            azure_ad_token_provider=token_provider,
            api_version=self.api_version,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format=response_format
        )

    def _get_termination_condition(self):
        """
        Define the termination condition for agent interactions.

        Returns:
            Condition or None: A combined condition object or None if no conditions are specified.
        """
        conditions = []

        if self.terminate_message is not None:
            conditions.append(TextMentionTermination(self.terminate_message))

        if self.max_rounds is not None:
            conditions.append(MaxMessageTermination(max_messages=self.max_rounds))

        if not conditions:
            return None

        termination_condition = conditions[0]
        for condition in conditions[1:]:
            termination_condition |= condition

        return termination_condition

    async def _summarize_conversation(self, history: list) -> str:
        """
        Summarize the conversation history.

        Parameters:
            history (list): A list of messages representing the conversation history.

        Returns:
            str: A summary of the conversation, including main topics, decisions, questions,
            unresolved issues, and document identifiers if mentioned.
        """
        if history:
            aoai = AzureOpenAIClient()
            prompt = (
                "Please summarize the following conversation, highlighting the main topics discussed, the specific subject "
                "if mentioned, any decisions made, questions raised, and any unresolved issues or actions pending. "
                "If there is a document or object mentioned with an identifying number, include that information for future reference. "
                "If there is there is no specific content or dialogue included to summarize you can say the conversation just started."                
                f"Conversation history: \n{history}"
            )
            conversation_summary = aoai.get_completion(prompt)
        else:
            conversation_summary = "The conversation just started."
        logging.info(f"[base_agent_strategy] Conversation summary: {conversation_summary[:200]}")
        return conversation_summary

    def _generate_security_ids(self, client_principal):
        """
        Generate security identifiers based on the client principal.

        Parameters:
            client_principal (dict): Information about the client principal, including the user ID
            and group names.

        Returns:
            str: A string representing the security identifiers, combining the user ID and group names.
        """
        security_ids = 'anonymous'
        if client_principal is not None:
            group_names = client_principal['group_names']
            security_ids = f"{client_principal['id']}" + (f",{group_names}" if group_names else "")
        return security_ids

    async def _read_prompt(self, prompt_name, placeholders=None):
        """
        Load and process a prompt file, applying strategy-based variants and placeholder replacements.

        This method reads a prompt file associated with a given agent, supporting optional variants
        (e.g., audio-optimized or text-only) and dynamic placeholder substitution.

        **Prompt Directory Structure**:
        - Prompts are stored in the `prompts/` directory.
        - If a strategy type is defined (`self.strategy_type`), the file is expected in a subdirectory:
          `prompts/<strategy_type>/`.

        **Prompt File Naming Convention**:
        - The filename is based on the provided `prompt_name`: `<prompt_name>.txt`.
        - You can pre-define variants externally using names like `<prompt_name>_audio.txt` or 
          `<prompt_name>_text_only.txt`, but this method does not automatically append suffixes. 
          Suffix logic must be handled when building `prompt_name`.

        **Placeholder Substitution**:
        - If a `placeholders` dictionary is provided, placeholders in the format `{{key}}` are replaced by
          their corresponding values.
        - If any `{{key}}` remains after substitution, the method checks for a fallback file:
          `prompts/common/<key>.txt`. If found, its content replaces the placeholder.
        - If no replacement is available, a warning is logged.

        **Example**:
        For `prompt_name='agent1_audio'` and `self.strategy_type='customer_service'`, the file path would be:
        `prompts/customer_service/agent1_audio.txt`

        **Parameters**:
        - prompt_name (str): The base name of the prompt file (without path, but may include variant suffix).
        - placeholders (dict, optional): Mapping of placeholder names to their substitution values.

        **Returns**:
        - str: Final content of the prompt with placeholders replaced.

        **Raises**:
        - FileNotFoundError: If the specified prompt file does not exist.
        """
 
        # Construct the prompt file path
        prompt_file_path = os.path.join(self._prompt_dir(), f"{prompt_name}.txt")

        if not os.path.exists(prompt_file_path):
            logging.error(f"[base_agent_strategy] Prompt file '{prompt_name}' not found: {prompt_file_path}.")
            raise FileNotFoundError(f"Prompt file '{prompt_name}' not found.")

        logging.info(f"[base_agent_strategy] Using prompt file path: {prompt_file_path}")
        
        # Read and process the selected prompt file
        with open(prompt_file_path, "r") as f:
            prompt = f.read().strip()
            
            # Replace placeholders provided in the 'placeholders' dictionary
            if placeholders:
                for key, value in placeholders.items():
                    prompt = prompt.replace(f"{{{{{key}}}}}", value)
            
            # Find any remaining placeholders in the prompt
            pattern = r"\{\{([^}]+)\}\}"
            matches = re.findall(pattern, prompt)
            
            # Process each unmatched placeholder
            for placeholder_name in set(matches):
                # Skip if placeholder was already replaced
                if placeholders and placeholder_name in placeholders:
                    continue
                # Look for a corresponding file in 'prompts/common'
                common_file_path = os.path.join("prompts", "common", f"{placeholder_name}.txt")
                if os.path.exists(common_file_path):
                    with open(common_file_path, "r") as pf:
                        placeholder_content = pf.read().strip()
                        prompt = prompt.replace(f"{{{{{placeholder_name}}}}}", placeholder_content)
                else:
                    # Log a warning if the placeholder cannot be replaced
                    logging.warning(
                        f"[base_agent_strategy] Placeholder '{{{{{placeholder_name}}}}}' could not be replaced."
                    )
            return prompt


        

    def _prompt_dir(self):
            """
            Returns the directory path for prompts based on the strategy type.
        
            If the 'strategy_type' attribute is not defined, a ValueError is raised.
            The directory path will include the strategy type as a subdirectory.
        
            Returns:
                str: The directory path for prompts.
            """
            if not hasattr(self, 'strategy_type'):
                raise ValueError("strategy_type is not defined")        
            prompts_dir = "prompts" + "/" + self.strategy_type.value
            return prompts_dir

    async def _get_model_context(self, history):
        """
        Add the conversation summary as the model context.
        """        
        history_summary = await self._summarize_conversation(history)
        initial_messages = []
        initial_messages.append(SystemMessage(content=f"Summary of Conversation History to Assist with Follow-Up Questions: {history_summary}"))
        return BufferedChatCompletionContext(buffer_size=self.context_buffer_size, initial_messages=initial_messages)
    

    async def _create_chat_closure_agent(self, output_format, output_mode):
        """
        Create a chat closure agent based on the specified output format and mode.

        Parameters:
            output_format (OutputFormat): The desired output format (e.g., TEXT_TTS, JSON, TEXT).
            output_mode (OutputMode): The desired output mode (e.g., STREAMING or non-streaming).

        Returns:
            AssistantAgent: The configured chat closure agent.

        Raises:
            ValueError: If output_format or output_mode is None.
        """
        if output_format is None or output_mode is None:
            raise ValueError("Both output_format and output_mode must be specified.")

        if output_format == OutputFormat.TEXT_TTS:
            prompt_name = "chat_closure_tts"
        elif output_format == OutputFormat.JSON:
            prompt_name = "chat_closure_json"
        elif output_format == OutputFormat.TEXT:
            prompt_name = "chat_closure_text"

        return AssistantAgent(
            name="chat_closure",
            system_message=await self._read_prompt(prompt_name),
            model_client=self._get_model_client() if output_mode == OutputMode.STREAMING else self._get_model_client(response_format=ChatGroupResponse),
            model_client_stream=True if output_mode == OutputMode.STREAMING else False
        )