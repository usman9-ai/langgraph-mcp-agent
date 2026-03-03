from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json

from .auth import authenticate_and_authorize_user, create_access_token
from .dependencies import verify_token
from .agent_wrapper import init_agent, run_agent_stream

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    await init_agent()


# --------------------
# 🔐 AUTH ENDPOINT
# --------------------

class LoginRequest(BaseModel):
    employee_id: str
    password: str


@app.post("/auth/login")
async def login(request: LoginRequest):
    authenticated, authorized = authenticate_and_authorize_user(
        request.employee_id,
        request.password
    )

    if not authenticated:
        # LDAP authentication failed
        raise HTTPException(status_code=401, detail="wrong credentials")

    if not authorized:
        # Authenticated but not authorized for this application
        raise HTTPException(status_code=403, detail="not authorized")

    token = create_access_token({"sub": request.employee_id})
    return {"access_token": token}


# --------------------
# 💬 CHAT ENDPOINT
# --------------------

class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
async def chat(request: ChatRequest, user=Depends(verify_token)):

    async def event_generator():
        open_event = {"type": "stream_open", "status": "connected"}
        yield f"event: stream_open\ndata: {json.dumps(open_event)}\n\n"
        async for chunk in run_agent_stream(request.message):
            event_name = chunk.get("type", "message")
            data = json.dumps(chunk, ensure_ascii=False)
            yield f"event: {event_name}\ndata: {data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
