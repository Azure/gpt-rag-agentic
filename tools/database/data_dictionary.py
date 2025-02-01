from typing import Annotated
from .types import TablesList, SchemaInfo
from connectors import CosmosDBClient

async def get_all_tables_info(datasource: Annotated[str, "Name of the target datasource"]) -> TablesList:
    """
    Retrieve a list of tables filtering by the given datasource. 
    Each entry will only have "table", "description", and "datasource".
    """
    cosmosdb = CosmosDBClient()

    # 1. Pull all documents from the `tables` container.
    documents = await cosmosdb.list_documents("tables")

    # 2. Filter and map each document if its 'datasource' matches the parameter.
    tables_info = []
    for doc in documents:
        if doc.get("datasource") == datasource:
            table_item = {
                "table": doc.get("table"),
                "description": doc.get("description"),
                "datasource": doc.get("datasource"),
            }
            tables_info.append(table_item)

    # 3. If none were found, return an empty list with an error message
    if not tables_info:
        return TablesList(
            tables=[],
            error=f"No datasource with name '{datasource}' was found."
        )

    # 4. Otherwise, return a TablesList of all matching tables
    return TablesList(tables=tables_info)


async def get_schema_info(
    datasource: Annotated[str, "Target datasource"],
    table_name: Annotated[str, "Target table"]
) -> SchemaInfo:
    """
    Retrieve schema information based on:
    - datasource (required)
    - table_name (required)

    Returns:
        SchemaInfo: An object containing the schema information or an error message.
    """
    cosmosdb = CosmosDBClient()

    # 1. Fetch all table documents from Cosmos DB
    all_tables_docs = await cosmosdb.list_documents("tables")

    # 2. Filter documents to those belonging to the provided datasource
    docs_for_datasource = [
        doc for doc in all_tables_docs
        if doc.get("datasource") == datasource
    ]

    # If no docs match this datasource, return an error
    if not docs_for_datasource:
        return SchemaInfo(
            error=f"Datasource '{datasource}' not found in data dictionary."
        )

    # 3. If a table_name is provided, look for that specific table in this datasource
    matching_table_doc = next(
        (doc for doc in docs_for_datasource if doc.get("table") == table_name),
        None
    )
    if not matching_table_doc:
        return SchemaInfo(
            error=f"Table '{table_name}' not found in datasource '{datasource}'."
        )

    # 4. Return schema information for the matched table

    columns = matching_table_doc.get("columns")
    if columns:
        columns = {name: description for name, description in columns.items()}


    return SchemaInfo(
        datasource=datasource,
        table=table_name,
        description=matching_table_doc.get("description"),
        columns=columns
    )
