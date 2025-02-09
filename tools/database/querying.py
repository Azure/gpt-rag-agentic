import sqlparse
from typing import Annotated
from .types import ValidateSQLQueryResult, ExecuteQueryResult
from connectors.cosmosdb import CosmosDBClient
from connectors.fabric import SQLEndpointClient, SemanticModelClient
from connectors.types import SQLEndpointConfig, SemanticModelConfig, SQLDatabaseConfig
from connectors.sqldbs import SQLDBClient

def validate_sql_query(query: Annotated[str, "SQL Query"]) -> ValidateSQLQueryResult:
    """
    Validate the syntax of an SQL query.
    Returns a ValidateSQLQueryResult indicating validity.
    """
    try:
        parsed = sqlparse.parse(query)
        if parsed and len(parsed) > 0:
            return ValidateSQLQueryResult(is_valid=True)
        else:
            return ValidateSQLQueryResult(is_valid=False, error="Query could not be parsed.")
    except Exception as e:
        return ValidateSQLQueryResult(is_valid=False, error=str(e))

async def execute_dax_query(datasource: Annotated[str, "Target datasource"], query: Annotated[str, "DAX Query"], access_token: Annotated[str, "User Access Token"]) -> ExecuteQueryResult:
    """
    Execute a DAX query against a semantic model datasource and return the results.
    """
    try:
        cosmosdb = CosmosDBClient()
        datasource_config = await cosmosdb.get_document('datasources', datasource)
        if not datasource_config or datasource_config.get("type") != "semantic_model":
            return ExecuteQueryResult(error=f"{datasource} datasource configuration not found or invalid for Semantic Model.")
    
        semantic_model_config = SemanticModelConfig(
            id=datasource_config.get("id"),
            description=datasource_config.get("description"),
            type=datasource_config.get("type"),
            organization=datasource_config.get("organization"),
            dataset=datasource_config.get("dataset"),
            workspace=datasource_config.get("workspace"),
            tenant_id=datasource_config.get("tenant_id"),
            client_id=datasource_config.get("client_id")
        ) 
        semantic_client = SemanticModelClient(semantic_model_config)
        results = await semantic_client.execute_restapi_dax_query(dax_query=query, user_token=access_token)
        return ExecuteQueryResult(results=results)
    except Exception as e:
        return ExecuteQueryResult(error=str(e))

async def execute_sql_query(
    datasource: Annotated[str, "Target datasource name"], 
    query: Annotated[str, "SQL Query"]
) -> ExecuteQueryResult:
    """
    Execute a SQL query against a SQL datasource and return the results.
    Supports both 'sql_endpoint' and 'sql_database' types.
    Only SELECT statements are allowed.
    """
    try:
        # Fetch the datasource configuration
        cosmosdb = CosmosDBClient()
        datasource_config = await cosmosdb.get_document('datasources', datasource)

        if not datasource_config:
            return ExecuteQueryResult(error=f"{datasource} datasource configuration not found.")

        # Determine datasource type and initialize the appropriate client
        datasource_type = datasource_config.get("type")
        
        if datasource_type == "sql_endpoint":
            sql_endpoint_config = SQLEndpointConfig(
                id=datasource_config.get("id"),
                description=datasource_config.get("description"),
                type=datasource_config.get("type"),
                organization=datasource_config.get("organization"),
                server=datasource_config.get("server"),
                database=datasource_config.get("database"),
                tenant_id=datasource_config.get("tenant_id"),
                client_id=datasource_config.get("client_id")
            )
            sql_client = SQLEndpointClient(sql_endpoint_config)

        elif datasource_type == "sql_database":
            sql_database_config = SQLDatabaseConfig(
                id=datasource_config.get("id"),
                description=datasource_config.get("description"),
                type=datasource_config.get("type"),
                server=datasource_config.get("server"),
                database=datasource_config.get("database"),
                uid=datasource_config.get("uid", None)
            )
            sql_client = SQLDBClient(sql_database_config)

        else:
            return ExecuteQueryResult(error="Datasource type not supported for SQL queries.")

        # Create a connection and execute the query
        connection = await sql_client.create_connection()
        cursor = connection.cursor()

        # Validate that only SELECT statements are allowed
        if not query.strip().lower().startswith('select'):
            return ExecuteQueryResult(error="Only SELECT statements are allowed.")

        cursor.execute(query)
        
        # Fetch and structure the results
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        results = [dict(zip(columns, row)) for row in rows]

        return ExecuteQueryResult(results=results)

    except Exception as e:
        # Handle any exceptions and return the error
        return ExecuteQueryResult(error=str(e))
