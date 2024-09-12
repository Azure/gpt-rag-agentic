from .default_agent_creation_strategy import DefaultAgentCreationStrategy

class AgentCreationStrategyFactory:
    @staticmethod
    def get_creation_strategy(strategy_type: str):
        if strategy_type == 'default':
            return DefaultAgentCreationStrategy()
        
        # Add other strategies here as needed.
        # Example: 
        # elif strategy_type == 'custom':
        #     return CustomAgentCreationStrategy()
        
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
