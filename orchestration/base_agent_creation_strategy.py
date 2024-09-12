import os

class BaseAgentCreationStrategy:
    def create_agents(self, llm_config, conversation_summary):
        raise NotImplementedError("This method should be overridden in subclasses.")
    
    def _read_prompt(self, agent_name, placeholders=None):
        prompts_dir = "prompts"
        file_path = os.path.join(prompts_dir, f"{agent_name}.txt")
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                prompt = f.read().strip()
                if placeholders:
                    for key, value in placeholders.items():
                        prompt = prompt.replace(f"{{{{{key}}}}}", value)
                return prompt
        else:
            raise FileNotFoundError(f"Prompt file for agent '{agent_name}' not found.")    
