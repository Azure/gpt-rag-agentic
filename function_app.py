# function_app.py
import asyncio
import os
import json
import logging
import warnings
import azure.functions as func
from azurefunctions.extensions.http.fastapi import Request, StreamingResponse, JSONResponse
from orchestration import RequestResponseOrchestrator, StreamingOrchestrator, OrchestratorConfig

# User Warning configuration
import warnings
# Available options for USER_WARNING_FILTER:
#   ignore  - never show the warning
#   always  - always show the warning
#   error   - turn the warning into an exception
#   once    - show the warning only once
#   module  - show the warning only once per module
#   default - default Python behavior
user_warning_filter = os.environ.get('USER_WARNING_FILTER', 'ignore').lower()
warnings.filterwarnings(user_warning_filter, category=UserWarning)

# Logging configuration
4
logging.getLogger("azure").setLevel(os.environ.get('AZURE_LOGLEVEL', 'WARNING').upper())
logging.getLogger("httpx").setLevel(os.environ.get('HTTPX_LOGLEVEL', 'ERROR').upper())
logging.getLogger("httpcore").setLevel(os.environ.get('HTTPCORE_LOGLEVEL', 'ERROR').upper())
logging.getLogger("openai._base_client").setLevel(os.environ.get('OPENAI_BASE_CLIENT_LOGLEVEL', 'WARNING').upper())
logging.getLogger("urllib3").setLevel(os.environ.get('URLLIB3_LOGLEVEL', 'WARNING').upper())
logging.getLogger("urllib3.connectionpool").setLevel(os.environ.get('URLLIB3_CONNECTIONPOOL_LOGLEVEL', 'WARNING').upper())
logging.getLogger("openai").setLevel(os.environ.get('OPENAI_LOGLEVEL', 'WARNING').upper())
logging.getLogger("autogen_core").setLevel(os.environ.get('AUTOGEN_CORE_LOGLEVEL', 'WARNING').upper())
logging.getLogger("autogen_core.events").setLevel(os.environ.get('AUTOGEN_EVENTS_LOGLEVEL', 'WARNING').upper())
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
        orchestrator = RequestResponseOrchestrator(conversation_id, OrchestratorConfig(), client_principal, access_token)
        result = await orchestrator.answer(question)
        return JSONResponse(content=result)
    else:
        return JSONResponse(content={"error": "no question found in json input"}, status_code=400)

@app.route(route="orcstream", methods=[func.HttpMethod.POST])
async def orchestrator_streaming(req: Request) -> StreamingResponse:
    data = await req.json()
    conversation_id = data.get("conversation_id")
    question = data.get("question")
    optimize_for_audio = data.get("optimize_for_audio", False)    

    # Gather client principal info (optional)
    client_principal = {
        "id": data.get("client_principal_id", "00000000-0000-0000-0000-000000000000"),
        "name": data.get("client_principal_name", "anonymous"),
        "group_names": data.get("client_group_names", "")
    }
    access_token = data.get("access_token", None)
    
    if question:
        orchestrator = StreamingOrchestrator(conversation_id, OrchestratorConfig(), client_principal, access_token)
        orchestrator.set_optimize_for_audio(optimize_for_audio)

        async def stream_generator():
            logging.info("[orcstream_endpoint] Entering stream_generator")
            last_yield = asyncio.get_event_loop().time()
            heartbeat_interval = 15  # seconds between heartbeats
            heartbeat_count = 0

            async for chunk in orchestrator.answer(question):
                now = asyncio.get_event_loop().time()
                # If the time since the last yield exceeds the heartbeat interval, send a heartbeat
                if now - last_yield >= heartbeat_interval:
                    heartbeat_count += 1
                    logging.info(f"Sending heartbeat #{heartbeat_count}")
                    yield "\n\n"
                    last_yield = now
                if chunk:
                    # logging.info(f"Yielding chunk: {chunk}")
                    # For text-only mode, yield the raw chunk; else, serialize to JSON.
                    yield chunk
                    last_yield = now
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    else:
        return JSONResponse(content={"error": "no question found in json input"}, status_code=400)
