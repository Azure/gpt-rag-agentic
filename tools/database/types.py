# Database Tools Models

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, Literal


class DataSourceItem(BaseModel):
    """
    Represents a data source with its type information.

    Attributes:
        name: The name of the data source.
        description: The description of the data source.        
        type: The type of the data source.
    """
    name: str
    description: str    
    type: str

class DataSourcesList(BaseModel):
    """
    Represents a list of available data sources.

    Attributes:
        datasources: A list of DataSourceItem instances, each containing information about a data source.
    """
    datasources: List[DataSourceItem]
    
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


# Database AI Search Index Retrieval Models

from pydantic import BaseModel, Field
from typing import List, Optional

class QueryItem(BaseModel):
    """
    Represents a single query retrieval result.

    Attributes:
        question: The question from the search result.
        query: The optimized query string.
        reasoning: Explanation or reasoning behind the query construction.
    """
    question: str = Field(..., description="The question from the search result")
    query: str = Field(..., description="The optimized query string")
    reasoning: str = Field(..., description="The reasoning behind the query construction")

class QueriesRetrievalResult(BaseModel):
    """
    Represents the overall result for queries retrieval.

    Attributes:
        queries (List[QueryItem]): A list of query retrieval results.
        error (Optional[str]): An error message, if any. Defaults to None.
    """
    queries: List[QueryItem] = Field(..., description="A list of query retrieval results")
    error: Optional[str] = Field(None, description="Error message if query fails")


# For tables_retrieval
class TableRetrievalItem(BaseModel):
    """
    Represents a single table entry with its name, description, and datasource.
    """
    table: str = Field(..., description="The name of the table")
    description: str = Field(..., description="A brief description of the table")
    datasource: Optional[str] = Field(None, description="The datasource used for retrieval")

class TablesRetrievalResult(BaseModel):
    """
    Represents the result for tables retrieval.

    Attributes:
        tables: A list of TableRetrievalItem objects.
        error (Optional[str]): An error message, if any. Defaults to None.
    """
    tables: List[TableRetrievalItem] = Field(..., description="List of tables with details")
    error: Optional[str] = Field(None, description="Error message if query fails") 

class MeasureItem(BaseModel):
    """
    Represents information about a specific measure.

    Attributes:
        name: The name of the measure.
        description: A brief description of the measure.
        datasource: The datasource where the measure resides.
        type: The type of the measure ("external" or "local").
        source_table: The source table associated with the measure.
        data_type: The data type of the measure.
        source_model: The source model for the measure.
    """
    name: str = Field(..., description="The name of the measure")
    description: str = Field(..., description="A brief description of the measure")
    datasource: str = Field(..., description="The datasource for the measure")
    type: Literal["external", "local"] = Field(..., description="The type of the measure (external or local)")
    source_table: Optional[str] = Field(None, description="The source table for the measure")
    data_type: Optional[str] = Field(None, description="The data type of the measure")
    source_model: Optional[str] = Field(None, description="The source model for the external measure")


class MeasuresList(BaseModel):
    """
    Represents a list of measures along with optional error information.

    Attributes:
        measures: A list of MeasureItem instances.
        error: An optional error message if issues occur.
    """
    measures: List[MeasureItem] = Field(..., description="List of measures with details")
    error: Optional[str] = Field(None, description="Error message if query fails")
