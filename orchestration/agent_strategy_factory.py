from .strategies.classic_rag_agent_strategy import ClassicRAGAgentStrategy
from .strategies.multimodal_agent_strategy import MultimodalAgentStrategy
# # NL2SQL Strategies
# from .strategies.nl2sql_standard_strategy import NL2SQLStandardStrategy
# from .strategies.nl2sql_advisor_strategy import NL2SQLAdvisorStrategy
# from .strategies.nl2sql_fewshot_strategy import NL2SQLFewshotStrategy
# from .strategies.nl2sql_fewshot_scaled_strategy import NL2SQLFewshotScaledStrategy

from .constants import CLASSIC_RAG, MULTIMODAL_RAG, NL2SQL, NL2SQL_ADVISOR, NL2SQL_FEWSHOT, NL2SQL_FEWSHOT_SCALED

class AgentStrategyFactory:
    @staticmethod
    def get_strategy(strategy_type: str):
        if strategy_type == CLASSIC_RAG:
            return ClassicRAGAgentStrategy()
        elif strategy_type == MULTIMODAL_RAG:
            return MultimodalAgentStrategy()        
        # elif strategy_type == NL2SQL:
        #     return NL2SQLStandardStrategy()
        # elif strategy_type == NL2SQL_ADVISOR or strategy_type == 'nl2sql_dual':
        #     return NL2SQLAdvisorStrategy()  
        # elif strategy_type == NL2SQL_FEWSHOT:
        #     return NL2SQLFewshotStrategy()      
        # elif strategy_type == NL2SQL_FEWSHOT_SCALED:
        #     return NL2SQLFewshotScaledStrategy()   
        
        
        # Add other strategies here as needed.
        # Example: 
        # elif strategy_type == 'custom':
        #     return CustomAgentStrategy()
        
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
