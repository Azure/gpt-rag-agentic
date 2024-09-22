import logging
import os

from connectors import AzureOpenAIClient

class BaseAgentCreationStrategy:
    def create_agents(self, llm_config, history):
        raise NotImplementedError("This method should be overridden in subclasses.")

    def _read_prompt(self, agent_name, placeholders=None):
        prompts_dir = "prompts"
        
        # Define the custom and default file paths
        custom_file_path = os.path.join(prompts_dir, f"{agent_name}.custom.txt")
        default_file_path = os.path.join(prompts_dir, f"{agent_name}.txt")
        
        # Check for the custom prompt file first
        if os.path.exists(custom_file_path):
            selected_file = custom_file_path
        elif os.path.exists(default_file_path):
            selected_file = default_file_path
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