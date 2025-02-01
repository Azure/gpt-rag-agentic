# Database AI Search Index Retrieval Models

from pydantic import BaseModel, Field
from typing import List

class QueryItem(BaseModel):
    """
    Represents a single query retrieval result.

    Attributes:
        question: The question from the search result.
        query: The optimized query string.
        selected_tables: A list of selected tables.
        selected_columns: A list of selected columns.
        reasoning: Explanation or reasoning behind the query construction.
    """
    question: str = Field(..., description="The question from the search result")
    query: str = Field(..., description="The optimized query string")
    selected_tables: List[str] = Field(..., description="List of selected tables")
    selected_columns: List[str] = Field(..., description="List of selected columns")
    reasoning: str = Field(..., description="The reasoning behind the query construction")

class QueriesRetrievalResult(BaseModel):
    """
    Represents the overall result for queries retrieval.

    Attributes:
        results: A list of query retrieval results.
    """
    results: List[QueryItem] = Field(..., description="A list of query retrieval results")



class ColumnItem(BaseModel):
    """
    Represents a single column with its table name, column name, and description.
    """
    table_name: str = Field(..., description="The name of the table")
    column_name: str = Field(..., description="The name of the column")
    description: str = Field(..., description="A description of the column")

class ColumnsRetrievalResult(BaseModel):
    """
    Represents the result for columns retrieval.
    
    Attributes:
        columns: A list of ColumnItem objects.
    """
    columns: List[ColumnItem] = Field(..., description="List of columns with their details")

# For tables_retrieval
class TableRetrievalItem(BaseModel):
    """
    Represents a single table entry with its name and description.
    """
    table_name: str = Field(..., description="The name of the table")
    description: str = Field(..., description="A brief description of the table")

class TablesRetrievalResult(BaseModel):
    """
    Represents the result for tables retrieval.

    Attributes:
        tables: A list of TableRetrievalItem objects.
    """
    tables: List[TableRetrievalItem] = Field(..., description="List of tables with details")

