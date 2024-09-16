from .classic_rag_agent_creation_strategy import ClassicRAGAgentCreationStrategy
from .nl2sql_agent_creation_strategy import NL2SQLAgentCreationStrategy

class AgentCreationStrategyFactory:
    @staticmethod
    def get_creation_strategy(strategy_type: str):
        if strategy_type == 'classic-rag':
            return ClassicRAGAgentCreationStrategy()
        elif strategy_type == 'nl2sql':
            return NL2SQLAgentCreationStrategy()
        
        # Add other strategies here as needed.
        # Example: 
        # elif strategy_type == 'custom':
        #     return CustomAgentCreationStrategy()
        
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
