import logging
import json
import os
import time
import azure.functions as func

from orchestration import Orchestrator

###############################################################################
# Pipeline Functions
###############################################################################

app = func.FunctionApp()

        
###################################################################################
# Orchestator function (HTTP Triggered by AI Search)
###################################################################################

        
@app.route(route="orc", auth_level=func.AuthLevel.FUNCTION)
async def orc(req: func.HttpRequest) -> func.HttpResponse:
    req_body = req.get_json()
    conversation_id = req_body.get('conversation_id')
    question = req_body.get('question')
    client_principal_id = req_body.get('client_principal_id')
    client_principal_name = req_body.get('client_principal_name') 
    if not client_principal_id or client_principal_id == '':
        client_principal_id = '00000000-0000-0000-0000-000000000000'
        client_principal_name = 'anonymous'    
    client_principal = {
        'id': client_principal_id,
        'name': client_principal_name
    }

    if question:

   
        orchestrator = Orchestrator(conversation_id, client_principal)

        result = await orchestrator.answer(question)

        return func.HttpResponse(json.dumps(result), mimetype="application/json", status_code=200)
    
    else:
        return func.HttpResponse('{"error": "no question found in json input"}', mimetype="application/json", status_code=200)
