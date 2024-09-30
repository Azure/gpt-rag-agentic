import logging
import os

from connectors import AzureOpenAIClient

class BaseAgentCreationStrategy:
    def __init__(self):
        pass

    def create_agents(self, llm_config, history):
        raise NotImplementedError("This method should be overridden in subclasses.")

    def _read_prompt(self, agent_name, placeholders=None):
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
            logging.info(f"[base_agent_creation_strategy] Using custom file path: {custom_file_path}")            
        elif os.path.exists(default_file_path):
            selected_file = default_file_path
            logging.info(f"[base_agent_creation_strategy] Using default file path: {default_file_path}")                  
        else:
            logging.error(f"[base_agent_creation_strategy] Prompt file for agent '{agent_name}' not found.")
            raise FileNotFoundError(f"Prompt file for agent '{agent_name}' not found.")
        
        # Read and process the selected prompt file
        with open(selected_file, "r") as f:
            prompt = f.read().strip()
            if placeholders:
                for key, value in placeholders.items():
                    prompt = prompt.replace(f"{{{{{key}}}}}", value)
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
    
    def _summarize_conversation(self, history: list) -> str:
        """Summarize the conversation history."""
        if history:
            aoai = AzureOpenAIClient()
            prompt = (
                "Summarize the conversation provided, identify its main points of discussion "
                f"and any conclusions that were reached. Conversation history: \n{history}"
            )
            conversation_summary = aoai.get_completion(prompt)
        else:
            conversation_summary = "The conversation just started."
        logging.info(f"[base_agent_creation_strategy] Conversation summary: {conversation_summary[:100]}")
        return conversation_summary