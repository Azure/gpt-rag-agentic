# function_app.py
import azure.functions as func
from azure.functions import AsgiMiddleware
from fast_api_app import app as fastapi_app

# Create the FunctionApp object.
app = func.FunctionApp()

# Route all incoming requests (adjust route as needed)
@app.route(route="{*path}", auth_level=func.AuthLevel.FUNCTION)
def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    return AsgiMiddleware(fastapi_app).handle(req)
