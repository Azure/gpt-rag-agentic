# function_app.py
import asyncio
import os
import json
import logging
import warnings
import azure.functions as func
from azurefunctions.extensions.http.fastapi import Request, StreamingResponse, JSONResponse
from orchestration import Orchestrator

# Logging configuration
import warnings
warnings.filterwarnings("ignore", category=UserWarning)        
logging.getLogger('azure').setLevel(logging.WARNING)
logging.basicConfig(level=os.environ.get('LOGLEVEL', 'DEBUG').upper(), force=True)
logging.getLogger("uvicorn.error").propagate = True
logging.getLogger("uvicorn.access").propagate = True

# Create the Function App with the desired auth level.
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="orc", methods=[func.HttpMethod.POST])
async def orc(req: Request) -> JSONResponse:
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
            last_yield = asyncio.get_event_loop().time()
            heartbeat_interval = 15  # seconds between heartbeats
            heartbeat_count = 0

            async for chunk in orchestrator.answer_stream(question, text_only=text_only):
                now = asyncio.get_event_loop().time()
                # If the time since the last yield exceeds the heartbeat interval, send a heartbeat
                if now - last_yield >= heartbeat_interval:
                    heartbeat_count += 1
                    logging.info(f"Sending heartbeat #{heartbeat_count}")
                    if text_only:
                        # SSE heartbeat: a comment line
                        yield "\n\n"
                    else:
                        yield json.dumps({"heartbeat": heartbeat_count})
                    last_yield = now
                if chunk:
                    logging.info(f"Yielding chunk: {chunk}")
                    # For text-only mode, yield the raw chunk; else, serialize to JSON.
                    yield chunk if text_only else json.dumps(chunk)
                    last_yield = now
        
        media_type = "text/event-stream" if text_only else "application/stream+json"
        return StreamingResponse(stream_generator(), media_type=media_type)
    else:
        return JSONResponse(content={"error": "no question found in json input"}, status_code=400)
