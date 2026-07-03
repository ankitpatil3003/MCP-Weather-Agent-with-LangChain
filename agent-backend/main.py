import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent import AgentConfigurationError, build_agent, run_agent

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)

DEFAULT_AGENT_HOST = "127.0.0.1"
DEFAULT_AGENT_PORT = 8001

agent = None
agent_error: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent, agent_error
    try:
        agent = await build_agent()
        agent_error = None
    except AgentConfigurationError as exc:
        agent = None
        agent_error = str(exc)
    except Exception as exc:
        agent = None
        agent_error = f"Failed to initialize agent: {exc}"
    yield


app = FastAPI(title="Weather Agent Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] | None = None


class ChatResponse(BaseModel):
    response: str = Field(..., description="Assistant reply text")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail=agent_error or "Agent is not available.",
        )

    history = (
        [item.model_dump() for item in request.history]
        if request.history
        else None
    )
    response_text = await run_agent(agent, request.message, history=history)
    return ChatResponse(response=response_text)


if __name__ == "__main__":
    host = os.getenv("AGENT_HOST", DEFAULT_AGENT_HOST)
    port = int(os.getenv("AGENT_PORT", str(DEFAULT_AGENT_PORT)))
    uvicorn.run("main:app", host=host, port=port, reload=False)
