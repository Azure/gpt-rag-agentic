from .strategies.classic_rag_agent_creation_strategy import ClassicRAGAgentCreationStrategy
from .strategies.nl2sql_single_agent_creation_strategy import NL2SQLSingleAgentCreationStrategy
from .strategies.nl2sql_dual_agent_creation_strategy import NL2SQLDualAgentCreationStrategy
from .strategies.nl2sql_single_agent_fewshot_creation_strategy import NL2SQLSingleAgentFewshotCreationStrategy
from .constants import CLASSIC_RAG, NL2SQL, NL2SQL_DUAL, NL2SQL_FEWSHOT

class AgentCreationStrategyFactory:
    @staticmethod
    def get_creation_strategy(strategy_type: str):
        if strategy_type == CLASSIC_RAG:
            return ClassicRAGAgentCreationStrategy()
        elif strategy_type == NL2SQL:
            return NL2SQLSingleAgentCreationStrategy()
        elif strategy_type == NL2SQL_DUAL:
            return NL2SQLDualAgentCreationStrategy()  
        elif strategy_type == NL2SQL_FEWSHOT:
            return NL2SQLSingleAgentFewshotCreationStrategy()               
        # Add other strategies here as needed.
        # Example: 
        # elif strategy_type == 'custom':
        #     return CustomAgentCreationStrategy()
        
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
