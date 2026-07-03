import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage
from langchain_groq import ChatGroq
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)

DEFAULT_MCP_SERVER_URL = "http://127.0.0.1:8000/mcp"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


class AgentConfigurationError(Exception):
    """Raised when required agent configuration is missing or invalid."""


def _require_groq_api_key() -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key or api_key == "your_groq_api_key_here":
        raise AgentConfigurationError(
            "GROQ_API_KEY is not set. Copy agent-backend/.env.example to "
            "agent-backend/.env and add your Groq API key."
        )
    return api_key


async def build_agent():
    """Connect to the MCP weather server and create a LangGraph ReAct agent."""
    api_key = _require_groq_api_key()
    model_name = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    mcp_server_url = os.getenv("MCP_SERVER_URL", DEFAULT_MCP_SERVER_URL)

    client = MultiServerMCPClient(
        {
            "weather": {
                "url": mcp_server_url,
                "transport": "streamable_http",
            }
        }
    )
    tools = await client.get_tools()

    llm = ChatGroq(model=model_name, api_key=api_key)
    return create_react_agent(model=llm, tools=tools)


def _history_to_messages(history: list[dict]) -> list:
    messages = []
    for item in history:
        role = item.get("role", "")
        content = item.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    return messages


async def run_agent(
    agent, message: str, history: list[dict] | None = None
) -> str:
    """Invoke the agent with a user message and optional chat history."""
    messages = _history_to_messages(history or [])
    messages.append(HumanMessage(content=message))

    result = await agent.ainvoke({"messages": messages})
    final_message = result["messages"][-1]
    return final_message.content
