import sqlparse
from typing import Annotated
from .models import ValidateSQLQueryResult, ExecuteQueryResult
from connectors import CosmosDBClient, SQLEndpointClient, SemanticModelClient, SQLDBClient

def validate_sql_query(query: Annotated[str, "SQL Query"]) -> ValidateSQLQueryResult:
    """
    Validate the syntax of an SQL query.
    Returns {'is_valid': True} if valid, or {'is_valid': False, 'error': 'error message'} if invalid.
    """
    try:
        parsed = sqlparse.parse(query)
        if parsed and len(parsed) > 0:
            return ValidateSQLQueryResult(is_valid=True)
        else:
            return ValidateSQLQueryResult(is_valid=False, error="Query could not be parsed.")
    except Exception as e:
        return ValidateSQLQueryResult(is_valid=False, error=str(e))

# TODO: Review this method implementation based on the reference and instrcutions provided in the task
async def execute_dax_query(datasource: Annotated[str, "Datasource name"] , query: Annotated[str, "DAX Query"]) -> ExecuteQueryResult:
    """
    Execute an DAX query and return the results.
    Returns a list of dictionaries, each representing a row.
    """
    try:
        cosmosdb = CosmosDBClient()
        datasource_config = await cosmosdb.get_document('datasources', datasource)
        semantic_model_client = SemanticModelClient(datasource_config)
        query_results = await semantic_model_client.execute(query)
        columns = [column[0] for column in query_results.description]
        rows = query_results.fetchall()
        results = [dict(zip(columns, row)) for row in rows]
        return ExecuteQueryResult(results=results)
    except Exception as e:
        return ExecuteQueryResult(error=str(e))

# TODO: Review this method implementation based on the reference and instrcutions provided in the task
async def execute_sql_query(datasource: Annotated[str, "Datasource name"] , query: Annotated[str, "SQL Query"]) -> ExecuteQueryResult:
    """
    Execute an SQL query and return the results.
    Returns a list of dictionaries, each representing a row.
    """
    try:
        cosmosdb = CosmosDBClient()
        datasource_config = await cosmosdb.get_document('datasources', datasource)
        # TODO: Attention here, this could be SQLDBClient instead of SQLEndpointClient depending on the configuration verify the datasoutce type to ajust the code!
        sql_client = SQLEndpointClient(datasource_config)
        connection = await sql_client.create_connection()
        cursor = connection.cursor()
        if not query.strip().lower().startswith('select'):
            return ExecuteQueryResult(error="Only SELECT statements are allowed.")
        cursor.execute(query)
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        results = [dict(zip(columns, row)) for row in rows]
        return ExecuteQueryResult(results=results)
    except Exception as e:
        return ExecuteQueryResult(error=str(e))