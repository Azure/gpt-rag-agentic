from abc import ABC, abstractmethod
from .base_agent_strategy import BaseAgentStrategy

class NL2SQLBaseStrategy(BaseAgentStrategy, ABC):

    def __init__(self):
        super().__init__()
    
    @abstractmethod
    async def create_agents(self, history, client_principal=None, access_token=None, output_mode=None, output_format=None):
        pass