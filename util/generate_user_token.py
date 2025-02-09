import os
import msal
import logging
import urllib.parse
import threading
import time
import asyncio
from wsgiref.simple_server import make_server
from dotenv import load_dotenv
from connectors.cosmosdb import CosmosDBClient
from connectors.keyvault import get_secret, generate_valid_secret_name

logging.basicConfig(level=logging.INFO)

GREEN_BOLD = "\033[1;32m"
YELLOW_BOLD = "\033[1;33m"
RESET_COLOR = "\033[0m"

def start_local_server(port, result_container):
    def app(environ, start_response):
        query = environ.get("QUERY_STRING", "")
        params = urllib.parse.parse_qs(query)
        if "code" in params and "state" in params:
            result_container["query_params"] = {k: v[0] for k, v in params.items()}
            response_body = b"Authentication complete. You can close this window."
        else:
            response_body = b"Authorization code or state not found."
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [response_body]

    server = make_server("localhost", port, app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server

def get_user_token(client_id, client_secret, tenant_id):
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    scopes = ["https://analysis.windows.net/powerbi/api/Dataset.Read.All"]
    redirect_uri = "http://localhost:8000"
    app = msal.ConfidentialClientApplication(client_id, authority=authority, client_credential=client_secret)

    auth_flow = app.initiate_auth_code_flow(scopes, redirect_uri=redirect_uri)
    print(f"{GREEN_BOLD}Please navigate to the following URL to sign in:{RESET_COLOR}")
    print(auth_flow["auth_uri"])

    result_container = {}
    server = start_local_server(8000, result_container)

    timeout = 120
    start_time = time.time()
    while "query_params" not in result_container and (time.time() - start_time) < timeout:
        time.sleep(1)
    server.shutdown()

    if "query_params" not in result_container:
        raise Exception("Timeout waiting for the authorization code.")

    result = app.acquire_token_by_auth_code_flow(auth_flow, result_container["query_params"])
    if "access_token" in result:
        return result["access_token"]
    else:
        raise Exception("Failed to obtain access token: " + str(result.get("error_description")))

async def main():
    load_dotenv()

    # Get datasource config
    datasource = os.getenv("FABRIC_DATASOURCE", None)
    cosmosdb = CosmosDBClient()
    datasource_config = await cosmosdb.get_document('datasources', datasource)

    if not datasource_config:
        print(f"Could not read datasource configuration for {datasource} from CosmosDB.")
        exit(1)

    client_id = datasource_config.get("client_id")
    tenant_id = datasource_config.get("tenant_id")

    kv_secret_name = generate_valid_secret_name(f"{datasource_config.get('id')}-secret")
    
    # Get secret using the async function
    client_secret = await get_secret(kv_secret_name)

    try:
        token = get_user_token(client_id, client_secret, tenant_id)
        print(f"{GREEN_BOLD}Access token obtained:{RESET_COLOR}")
        print(f"{YELLOW_BOLD}{token}{RESET_COLOR}")
    except Exception as e:
        logging.error(f"Error obtaining access token: {e}")

if __name__ == "__main__":
    asyncio.run(main())
