# Database Tools Models

from pydantic import BaseModel
from typing import Dict, List, Optional, Union

class DataSourcesList(BaseModel):
    """
    Represents a list of available data sources.

    Attributes:
        datasources: A list of dictionaries containing the data source information.
    """
    datasources: List[Dict[str, Union[str, List[str]]]]

class TableItem(BaseModel):
    """
    Represents information about a specific database table.

    Attributes:
        table: The name of the table.
        description: A brief description of the table.
        datasource: The name of the data source where the table resides.
    """
    table: str
    description: str
    datasource: str

class TablesList(BaseModel):
    """
    Represents a list of tables along with optional error information.

    Attributes:
        tables: A list of TableItem instances, each representing a table.
        error: An optional error message, if any issues were encountered.
    """
    tables: List[TableItem]
    error: Optional[str] = None

class SchemaInfo(BaseModel):
    """
    Represents the schema details of a database table.

    Attributes:
        datasource: The name of the data source where the table resides.
        table: The name of the table.
        description: An optional description of the table.
        columns: A dictionary mapping column names to their respective descriptions.
    """
    datasource: str
    table: str
    description: Optional[str] = None
    columns: Optional[Dict[str, str]] = None  # Map column names to descriptions

class ValidateSQLQueryResult(BaseModel):
    """
    Represents the result of a SQL query validation.

    Attributes:
        is_valid: Indicates whether the SQL query is valid.
        error: An optional error message if the query is invalid.
    """
    is_valid: bool
    error: Optional[str] = None

class ExecuteQueryResult(BaseModel):
    """
    Represents the result of executing a SQL query.

    Attributes:
        results: A list of dictionaries representing the query results. 
                 Each dictionary maps column names to their respective values.
        error: An optional error message if the query execution failed.
    """
    results: Optional[List[Dict[str, Union[str, int, float, None]]]] = None
    error: Optional[str] = None