import json
import logging
import os
import azure.functions as func
from orchestration import Orchestrator


###############################################################################
# Logging Configuration
###############################################################################

default_log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
autogen_log_level = os.getenv('AUTOGEN_LOG_LEVEL', 'WARNING').upper()

logging.basicConfig(level=getattr(logging, default_log_level))
logging.getLogger('autogen_core').setLevel(getattr(logging, autogen_log_level))
logging.getLogger('autogen_agentchat').setLevel(getattr(logging, autogen_log_level))

###############################################################################
# Pipeline Functions
###############################################################################

app = func.FunctionApp()

###################################################################################
# Orchestator function (HTTP Triggered by AI Search)
###################################################################################

        
@app.route(route="orc", auth_level=func.AuthLevel.FUNCTION)
async def orc(req: func.HttpRequest) -> func.HttpResponse:
    try:
        logging.info("Logging initialized with LOG_LEVEL: %s and AUTOGEN_LOG_LEVEL: %s", default_log_level, autogen_log_level)

        req_body = req.get_json()

        # Get input parameters
        conversation_id = req_body.get('conversation_id')
        question = req_body.get('question')

        # Get client principal information
        client_principal_id = req_body.get('client_principal_id', '00000000-0000-0000-0000-000000000000')
        client_principal_name = req_body.get('client_principal_name', 'anonymous')
        client_group_names = req_body.get('client_group_names', '')
        client_principal = {
            'id': client_principal_id,
            'name': client_principal_name,
            'group_names': client_group_names        
        }

        # Call orchestrator
        if question:
            orchestrator = Orchestrator(conversation_id, client_principal)
            result = await orchestrator.answer(question)
            return func.HttpResponse(
                json.dumps(result),
                mimetype="application/json",
                status_code=200
            )
        else:
            return func.HttpResponse(
                json.dumps({"error": "no question found in json input"}),
                mimetype="application/json",
                status_code=400
            )
    except Exception as e:
        logging.error(f"Error processing request: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            mimetype="application/json",
            status_code=500
        )