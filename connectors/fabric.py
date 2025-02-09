import logging
import pyodbc
import asyncio
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from azure.identity.aio import ClientSecretCredential

from connectors.keyvault import get_secret, generate_valid_secret_name
from connectors.types import SQLEndpointConfig, SemanticModelConfig

class SQLEndpointClient:
    """
    Client for connecting to Fabric SQL Endpoint using a service principal.
    """
    def __init__(self, datasource_config):
        # Validate and parse the configuration using Pydantic
        if not isinstance(datasource_config, SQLEndpointConfig):
            datasource_config = SQLEndpointConfig.model_validate(datasource_config)
        self.datasource_config = datasource_config

    async def create_connection(self):
        """Create and return a connection using pyodbc."""
        return await self._create_sqlendpoint_connection()

    async def _create_sqlendpoint_connection(self):
        server = self.datasource_config.server
        database = self.datasource_config.database
        client_id = self.datasource_config.client_id
        tenant_id = self.datasource_config.tenant_id
        # Format service principal ID as client_id@tenant_id
        service_principal_id = f"{client_id}@{tenant_id}"
        # Retrieve the client secret from Key Vault using the datasource id
        kv_secret_name = generate_valid_secret_name(f"{self.datasource_config.id}-secret")
        # pyodbc is synchronous so we run the async secret call in an event loop
        client_secret = await get_secret(kv_secret_name)

        connection_string = (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={service_principal_id};"
            f"PWD={client_secret};"
            f"Authentication=ActiveDirectoryServicePrincipal"
        )
        try:
            connection = await asyncio.to_thread(pyodbc.connect, connection_string)
            return connection
        except Exception as e:
            logging.error(f"[fabric] Failed to connect to the SQL endpoint with service principal: {e}")
            raise


class SemanticModelClient:
    """
    Client for executing DAX queries against a Fabric semantic model (Power BI)
    using a service principal.
    """
    def __init__(self, datasource_config):
        if not isinstance(datasource_config, SemanticModelConfig):
            datasource_config = SemanticModelConfig.model_validate(datasource_config)
        self.datasource_config = datasource_config

    async def _get_restapi_access_token(self) -> str:
        """
        Obtain an access token using ClientSecretCredential.
        """
        kv_secret_name = generate_valid_secret_name(f"{self.datasource_config.id}-secret")
        client_secret = await get_secret(kv_secret_name)
        credential = ClientSecretCredential(
            tenant_id=self.datasource_config.tenant_id,
            client_id=self.datasource_config.client_id,
            client_secret=client_secret
        )
        try:
            token = await credential.get_token("https://analysis.windows.net/powerbi/api/.default")
            logging.info("[fabric] Access token acquired successfully for Semantic Model.")
            return token.token
        except Exception as e:
            logging.error(f"[fabric] Failed to obtain access token for Semantic Model: {e}")
            raise
        finally:
            await credential.close()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(aiohttp.ClientError)
    )
    async def execute_restapi_dax_query(self, dax_query: str, user_token: str = None, impersonated_user: str = None) -> list:
        """
        Execute a DAX query against the semantic model endpoint.
        Returns a list of dictionaries representing the query rows.
        """

        access_token = user_token

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }

        # Construct the URL using the dataset from the configuration.
        # url = f"https://api.powerbi.com/v1.0/myorg/groups/{self.datasource_config.workspace}/datasets/f72fb57e-80bf-4155-9c20-53ee4539e8b9/executeQueries"
        url = f"https://api.powerbi.com/v1.0/myorg/datasets/{self.datasource_config.dataset}/executeQueries"
        logging.info(f"[fabric] Rest API endpoint: {url}.")
        body = {
            "queries": [{"query": dax_query}],
            "serializerSettings": {"includeNulls": True}
        }
        if impersonated_user:
            body["impersonatedUserName"] = impersonated_user

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body) as response:
                if response.status == 200:
                    response_json = await response.json()
                    results = response_json.get('results', [])
                    if not results:
                        logging.warning("[fabric] No results found in the DAX query response.")
                        return []
                    tables = results[0].get('tables', [])
                    if not tables:
                        logging.warning("[fabric] No tables found in the DAX query response.")
                        return []
                    table = tables[0]
                    rows = table.get('rows', [])
                    columns = table.get('columns', [])
                    col_names = [col.get("name", f"Column{i}") for i, col in enumerate(columns)]
                    # If column names are available, zip them with each row.
                    if rows and col_names and len(col_names) == len(rows[0]):
                        results_list = [dict(zip(col_names, row)) for row in rows]
                    else:
                        results_list = rows
                    logging.info("[fabric] DAX query executed successfully on Semantic Model.")
                    return results_list
                elif response.status == 429:
                    retry_after = response.headers.get("Retry-After")
                    wait_time = int(retry_after) if retry_after else 0
                    logging.warning(f"[fabric] Rate limited. Retrying after {wait_time} seconds.")
                    await asyncio.sleep(wait_time)
                    raise aiohttp.ClientError("Rate limited")
                elif 400 <= response.status < 500:
                    error_message = await response.text()
                    logging.error(f"[fabric] Client error executing DAX query. Status: {response.status}, Message: {error_message}")
                    raise aiohttp.ClientError(f"Client error: {response.status} - {error_message}")
                else:
                    error_message = await response.text()
                    logging.error(f"[fabric] Server error executing DAX query. Status: {response.status}, Message: {error_message}")
                    raise aiohttp.ClientError(f"Server error: {response.status}")

    async def create_connection(self):
        """
        For interface consistency. Semantic Model operations do not maintain a persistent connection.
        """
        return self