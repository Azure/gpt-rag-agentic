# AI Search Index Retrieval Models

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union

class VectorIndexRetrievalResult(BaseModel):
    """
    Represents the result of a vector index retrieval operation.

    Attributes:
        result (str): A string containing the search results.
        error (Optional[str]): An error message, if any. Defaults to None.
    """
    result: str = Field(..., description="Search result string from vector index retrieval")
    error: Optional[str] = Field(None, description="Error message if query fails")


class MultimodalVectorIndexRetrievalResult(BaseModel):
    """
    Represents the result of a multimodal vector index retrieval.

    Attributes:
        texts (List[str]): A list of text snippets retrieved.
        captions (List[str]): A list of image captions.           
        images (List[List[str]]): A list where each element is a list of image URLs corresponding to a document.
        error (Optional[str]): An error message, if any. Defaults to None.
    """
    texts: List[str] = Field(..., description="List of text snippets retrieved")
    captions: List[str] = Field(..., description="List of image captions")        
    images: List[List[str]] = Field(...,description="List of lists of image URLs; each inner list corresponds to a document's related images")
    error: Optional[str] = Field(None, description="Error message if query fails")

# (Optional) For get_data_points_from_chat_log
class DataPointsResult(BaseModel):
    """
    Represents the result containing data points extracted from a chat log.

    Attributes:
        data_points: A list of strings where each string is a data point (e.g. a filename with extension).
    """
    data_points: List[str] = Field(..., description="List of extracted data points from the chat log")