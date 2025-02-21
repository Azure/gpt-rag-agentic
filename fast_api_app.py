# fast_api_app.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
import asyncio
import json

from orchestration import Orchestrator

class RemovePrefixMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, prefix: str):
        super().__init__(app)
        self.prefix = prefix

    async def dispatch(self, request: Request, call_next):
        # If the URL path starts with the prefix, remove it.
        if request.url.path.startswith(self.prefix):
            request.scope["path"] = request.url.path[len(self.prefix):] or "/"
        response = await call_next(request)
        return response

app = FastAPI()
# Strip the "/api" prefix that Azure Functions adds.
app.add_middleware(RemovePrefixMiddleware, prefix="/api")

@app.post("/orc")
async def orc_endpoint(request: Request):
    data = await request.json()
    conversation_id = data.get("conversation_id")
    question = data.get("question")

    # Get client principal information (optional)
    client_principal_id = data.get('client_principal_id', '00000000-0000-0000-0000-000000000000')
    client_principal_name = data.get('client_principal_name', 'anonymous')
    client_group_names = data.get('client_group_names', '')
    client_principal = {
        'id': client_principal_id,
        'name': client_principal_name,
        'group_names': client_group_names        
    }

    # Get access token (optional)
    access_token = data.get('access_token', None)
    
    if question:
        orchestrator = Orchestrator(conversation_id, client_principal, access_token)
        result = await orchestrator.answer(question)
        return JSONResponse(content=result)
    else:
        return JSONResponse(content={"error": "no question found in json input"}, status_code=400)

@app.post("/orcstream")
async def orcstream_endpoint(request: Request):
    data = await request.json()
    conversation_id = data.get("conversation_id")
    question = data.get("question")
    
    # Get client principal information (optional)
    client_principal_id = data.get('client_principal_id', '00000000-0000-0000-0000-000000000000')
    client_principal_name = data.get('client_principal_name', 'anonymous')
    client_group_names = data.get('client_group_names', '')
    client_principal = {
        'id': client_principal_id,
        'name': client_principal_name,
        'group_names': client_group_names        
    }
    
    # Get access token (optional)
    access_token = data.get('access_token', None)
    
    if question:
        orchestrator = Orchestrator(conversation_id, client_principal, access_token)
        
        async def stream_generator():
            async for chunk in orchestrator.answer_stream(question):
                yield chunk.encode("utf-8")
        
        return StreamingResponse(stream_generator(), media_type="text/plain")
    else:
        return JSONResponse(content={"error": "no question found in json input"}, status_code=400)
