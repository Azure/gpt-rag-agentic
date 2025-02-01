from .types import DataSourcesList
from connectors import CosmosDBClient

async def get_all_datasources_info() -> DataSourcesList:
    """
    Retrieve a list of all datasources.
    Returns a DataSourcesList object.
    """
    # 1. Pull all documents from the `datasources` container.
    cosmosdb = CosmosDBClient()
    documents = await cosmosdb.list_documents("datasources")

    datasources_info = []

    # 2. Process each document.
    for doc in documents:
        # Create a new record whose "datasource" is the doc's "id"
        record = {"id": doc.get("id")}

        # Copy over all fields except the Cosmos internal ones (those starting with `_`)
        # and except `id`, which we already used as "datasource".
        for key, value in doc.items():
            if not key.startswith("_") and key != "id":
                record[key] = value

        datasources_info.append(record)

    # 3. Return as DataSourcesList
    return DataSourcesList(datasources=datasources_info)