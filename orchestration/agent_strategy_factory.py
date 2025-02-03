# Typical RAG Strategies
from .strategies.classic_rag_agent_strategy import ClassicRAGAgentStrategy
from .strategies.multimodal_agent_strategy import MultimodalAgentStrategy
# NL2SQL Strategies
from .strategies.nl2sql_standard_strategy import NL2SQLStandardStrategy
from .strategies.nl2sql_fewshot_strategy import NL2SQLFewshotStrategy
from .strategies.nl2sql_fewshot_scaled_strategy import NL2SQLFewshotScaledStrategy
# Other Strategies
from .strategies.chat_with_fabric_strategy import ChatWithFabricStrategy

from .constants import CLASSIC_RAG, MULTIMODAL_RAG, NL2SQL, NL2SQL_FEWSHOT, NL2SQL_FEWSHOT_SCALED, CHAT_WITH_FABRIC

class AgentStrategyFactory:
    @staticmethod
    def get_strategy(strategy_type: str):
        if strategy_type == CLASSIC_RAG:
            return ClassicRAGAgentStrategy()
        elif strategy_type == MULTIMODAL_RAG:
            return MultimodalAgentStrategy()        
        elif strategy_type == CHAT_WITH_FABRIC:
            return ChatWithFabricStrategy()    
        elif strategy_type == NL2SQL:
            return NL2SQLStandardStrategy()
        elif strategy_type == NL2SQL_FEWSHOT:
            return NL2SQLFewshotStrategy()      
        elif strategy_type == NL2SQL_FEWSHOT_SCALED:
            return NL2SQLFewshotScaledStrategy()
           
        # Add other strategies here as needed.
        # Example: 
        # elif strategy_type == 'custom':
        #     return CustomAgentStrategy()
        
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
