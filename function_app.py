# function_app.py
import azure.functions as func
from azurefunctions.extensions.http.fastapi import Request, StreamingResponse, JSONResponse
import json
from orchestration import Orchestrator
import logging

# Create the Function App with the desired auth level.
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="orc", methods=[func.HttpMethod.POST])
async def orchestrator(req: Request) -> JSONResponse:
    data = await req.json()
    conversation_id = data.get("conversation_id")
    question = data.get("question")

    # Gather client principal info (optional)
    client_principal = {
        "id": data.get("client_principal_id", "00000000-0000-0000-0000-000000000000"),
        "name": data.get("client_principal_name", "anonymous"),
        "group_names": data.get("client_group_names", "")
    }
    access_token = data.get("access_token", None)
    
    if question:
        orchestrator = Orchestrator(conversation_id, client_principal, access_token)
        result = await orchestrator.answer(question)
        return JSONResponse(content=result)
    else:
        return JSONResponse(content={"error": "no question found in json input"}, status_code=400)

@app.route(route="orcstream", methods=[func.HttpMethod.POST])
async def orchestrator_streaming(req: Request) -> StreamingResponse:
    data = await req.json()
    conversation_id = data.get("conversation_id")
    question = data.get("question")
    text_only = data.get("text_only", False)

    # Gather client principal info (optional)
    client_principal = {
        "id": data.get("client_principal_id", "00000000-0000-0000-0000-000000000000"),
        "name": data.get("client_principal_name", "anonymous"),
        "group_names": data.get("client_group_names", "")
    }
    access_token = data.get("access_token", None)
    
    if question:
        orchestrator = Orchestrator(conversation_id, client_principal, access_token)
        
        async def stream_generator():
            logging.info("[orcstream_endpoint] Entering stream_generator")
            async for chunk in orchestrator.answer_stream(question, text_only=text_only):
                if text_only:
                    yield chunk  # Assuming chunk is already a string.
                else:
                    yield json.dumps(chunk)
        
        media_type = "text/event-stream" if text_only else "application/stream+json"
        return StreamingResponse(stream_generator(), media_type=media_type)
    else:
        return JSONResponse(content={"error": "no question found in json input"}, status_code=400)
