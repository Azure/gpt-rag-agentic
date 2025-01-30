import logging
import json
import os
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Union
from pydantic import BaseModel

class DataSourceInfo(BaseModel):
    datasource_name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    database: Optional[str] = None    
    error: Optional[str] = None

def get_data_sources_info(self, table_name=None, column_name=None) -> SchemaInfo:
    """
    Retrieve schema information from the data dictionary.
    If table_name is provided, returns the table description and columns.
    If column_name is provided, returns the column description.
    """
    if table_name:
        table_info = self.data_dictionary.get(table_name)
        if table_info:
            return SchemaInfo(
                table_name=table_name,
                description_long=table_info.get("description_long"),
                description_short=table_info.get("description_short"),
                columns=table_info.get("columns")
            )
        else:
            return SchemaInfo(error=f"Table '{table_name}' not found in data dictionary.")
    elif column_name:
        for table, info in self.data_dictionary.items():
            columns = info["columns"]
            if column_name in columns:
                return SchemaInfo(
                    table_name=table,
                    column_name=column_name,
                    column_description=columns[column_name]
                )
        return SchemaInfo(error=f"Column '{column_name}' not found in data dictionary.")
    else:
        return SchemaInfo(error="Please provide either 'table_name' or 'column_name'.")