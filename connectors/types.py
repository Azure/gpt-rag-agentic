from pydantic import BaseModel
from typing import Optional

class DataSourceConfig(BaseModel):
    id: str
    description: str
    type: str

class SQLEndpointConfig(DataSourceConfig):
    server: str
    database: str
    tenant_id: str
    client_id: str

class SemanticModelConfig(DataSourceConfig):
    organization: str
    workspace: str
    dataset: str
    tenant_id: str
    client_id: str

class SQLDatabaseConfig(DataSourceConfig):
    server: str
    database: str
    uid: Optional[str] = None