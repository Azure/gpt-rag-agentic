from .types import DataSourcesList, DataSourceItem
import os
from connectors import CosmosDBClient

async def get_all_datasources_info() -> DataSourcesList:
    """
    Retrieve a list of all datasources.
    Returns a DataSourcesList object with only 'datasource_name' and 'datasource_type'.
    """
    # 1. Pull all documents from the `datasources` container.
    cosmosdb = CosmosDBClient()
    datasources_container = os.environ.get('DATASOURCES_CONTAINER', 'datasources')
    documents = await cosmosdb.list_documents(datasources_container)

    datasources_info = []

    # 2. Process each document.
    for doc in documents:
        # Create a DataSourceItem with the required fields
        datasource_item = DataSourceItem(
            name=doc.get("id", ""),
            description=doc.get("description", ""),            
            type=doc.get("type", "")
        )
        datasources_info.append(datasource_item)

    # 3. Return as DataSourcesList
    return DataSourcesList(datasources=datasources_info)
