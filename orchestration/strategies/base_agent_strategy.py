import logging
import os
import re

from connectors import AzureOpenAIClient
from azure.identity import ManagedIdentityCredential, AzureCliCredential, ChainedTokenCredential, get_bearer_token_provider
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination

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

    async def create_agents(self, history, client_principal=None):
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

    def _get_agent_configuration(self):
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

    async def _read_prompt(self, agent_name, placeholders=None):
        """
        Reads the prompt file for a given agent, checking for custom or default files.

        The method searches for prompt files within the `prompts` directory. 
        It first looks for a custom prompt file and falls back to a default prompt 
        if the custom file does not exist.

        **Prompt Directory Location**:
        - The base prompt directory is named `prompts`. If the strategy has a 
        `strategy_type`, the prompt files are located in a subdirectory named 
        after that strategy (e.g., `prompts/strategy_name`).

        **Prompt File Naming**:
        - Custom prompt file: `{agent_name}.custom.txt`
        - Default prompt file: `{agent_name}.txt`

        **Prompt Lookup**:
        - If `{agent_name}.custom.txt` exists, it is read.
        - If not, `{agent_name}.txt` is read.
        - If neither file exists, a `FileNotFoundError` is raised.

        **Placeholder Replacement**:
        - If `placeholders` are provided, any placeholder in the prompt following 
        the format `{{placeholder_name}}` will be replaced with the corresponding 
        value from `placeholders`.
        - For any remaining placeholders not replaced (i.e., not in `placeholders`), 
        the method will search for a file named `placeholder_name.txt` in the 
        `prompts/common` directory. If the file exists, the placeholder will be replaced 
        with the content of that file.

        **Examples**:
        For an agent named `agent1` and a strategy type `customer_service`, the 
        following files are searched:
        1. `prompts/customer_service/agent1.custom.txt`
        2. `prompts/customer_service/agent1.txt`
        
        Parameters:
        - agent_name (str): The name of the agent for which the prompt is being read.
        - placeholders (dict, optional): A dictionary of placeholder names and 
        their corresponding values to replace in the prompt.

        Returns:
        - str: The content of the prompt file with placeholders replaced if applicable.

        Raises:
        - FileNotFoundError: If neither a custom nor a default prompt file is found.
        """        
        # Define the custom and default file paths
        custom_file_path = os.path.join(self._prompt_dir(), f"{agent_name}.custom.txt")
        default_file_path = os.path.join(self._prompt_dir(), f"{agent_name}.txt")
                                 
        # Check for the custom prompt file first
        if os.path.exists(custom_file_path):
            selected_file = custom_file_path
            logging.info(f"[base_agent_strategy] Using custom file path: {custom_file_path}")            
        elif os.path.exists(default_file_path):
            selected_file = default_file_path
            logging.info(f"[base_agent_strategy] Using default file path: {default_file_path}")                  
        else:
            logging.error(f"[base_agent_strategy] Prompt file for agent '{agent_name}' not found.")
            raise FileNotFoundError(f"Prompt file for agent '{agent_name}' not found.")
        
        # Read and process the selected prompt file
        with open(selected_file, "r") as f:
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
            prompts_dir = "prompts" + "/" + self.strategy_type
            return prompts_dir