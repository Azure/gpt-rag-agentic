from .classic_rag_agent_creation_strategy import ClassicRAGAgentCreationStrategy
from .nl2sql_agent_creation_strategy import NL2SQLAgentCreationStrategy
from .nl2sql_duo_agent_creation_strategy import NL2SQLDuoAgentCreationStrategy
from .constants import CLASSIC_RAG, NL2SQL, NL2SQL_DUO

class AgentCreationStrategyFactory:
    @staticmethod
    def get_creation_strategy(strategy_type: str):
        if strategy_type == CLASSIC_RAG:
            return ClassicRAGAgentCreationStrategy()
        elif strategy_type == NL2SQL:
            return NL2SQLAgentCreationStrategy()
        elif strategy_type == NL2SQL_DUO:
            return NL2SQLDuoAgentCreationStrategy()        
        # Add other strategies here as needed.
        # Example: 
        # elif strategy_type == 'custom':
        #     return CustomAgentCreationStrategy()
        
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
