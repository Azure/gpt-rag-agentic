# AI Search Index Retrieval Models

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union

# For vector_index_retrieve
class VectorIndexRetrievalResult(BaseModel):
    """
    Represents the result of a vector index retrieval operation.

    Attributes:
        result: A string containing the search results.
    """
    result: str = Field(..., description="Search result string from vector index retrieval")


# For multimodal_vector_index_retrieve
class MultimodalVectorIndexRetrievalResult(BaseModel):
    """
    Represents the result of a multimodal vector index retrieval.

    Attributes:
        texts: A list of text snippets retrieved.
        images: A list where each element is a list of image URLs corresponding to a document.
    """
    texts: List[str] = Field(..., description="List of text snippets retrieved")
    images: List[List[str]] = Field(
        ...,
        description="List of lists of image URLs; each inner list corresponds to a document's related images"
    )


# (Optional) For get_data_points_from_chat_log
class DataPointsResult(BaseModel):
    """
    Represents the result containing data points extracted from a chat log.

    Attributes:
        data_points: A list of strings where each string is a data point (e.g. a filename with extension).
    """
    data_points: List[str] = Field(..., description="List of extracted data points from the chat log")