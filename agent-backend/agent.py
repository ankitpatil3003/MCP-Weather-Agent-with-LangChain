import os
import re
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)

DEFAULT_MCP_SERVER_URL = "http://127.0.0.1:8000/mcp"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_GROQ_TEMPERATURE = 0.0
MAX_AGENT_ATTEMPTS = 3
MAX_HISTORY_MESSAGES = 20

_MALFORMED_TOOL_CALL_PATTERN = re.compile(
    r"<function[^>]*>.*?</function>|"
    r"\[TOOL:\s*[^\]]+\]|"
    r"<\|tool_call\|>.*?<\|/tool_call\|>",
    re.IGNORECASE | re.DOTALL,
)

_TOOL_RETRY_REMINDER = (
    "Reminder: invoke weather tools only through the native tool-calling interface. "
    "Do not output XML tags, markdown tool blocks, or text that simulates a function call."
)

SYSTEM_PROMPT = SystemMessage(
    content="""You are a weather assistant. Answer questions about weather anywhere in the world.

Rules:
- Always use the available weather tools for current conditions, forecasts, and geocoding. Never guess or invent weather data.
- When a tool returns a JSON object with an "error" field, explain the problem clearly to the user instead of making up an answer.
- Report temperatures in degrees Celsius (°C). Include the city and country when available.
- For forecast questions, use get_forecast with an appropriate number of days (1–5).
- For current conditions, use get_current_weather.
- If a city name is ambiguous (e.g. Springfield), ask the user which city or country they mean before calling tools.
- For comparisons across multiple cities, call the weather tool once per city, then synthesize the answer.
- Keep answers concise and conversational unless the user asks for detail.

Tool calling (critical — follow exactly):
- Invoke tools ONLY through the native tool-calling interface. The runtime executes tools for you; do not simulate tool calls in text.
- NEVER write tool calls as plain text, XML, markdown, or pseudo-code. Forbidden examples:
  - <function=geocode_city={"city": "Havana"}></function>
  - [TOOL: geocode_city(city="Havana")]
  - Calling geocode_city({"city": "Havana"}) inside your reply text
- Use only these tool names with structured arguments:
  - geocode_city — argument: city (string)
  - get_current_weather — argument: city (string)
  - get_forecast — arguments: city (string), days (integer 1–5, optional)
- If a tool call fails, retry via the native tool interface. Do not fall back to XML or text-based tool syntax."""
)


class AgentConfigurationError(Exception):
    """Raised when required agent configuration is missing or invalid."""


class AgentInvocationError(Exception):
    """Raised when the agent fails after retries."""


def _groq_temperature() -> float:
    raw = os.getenv("GROQ_TEMPERATURE", str(DEFAULT_GROQ_TEMPERATURE)).strip()
    try:
        return float(raw)
    except ValueError as exc:
        raise AgentConfigurationError(
            f"GROQ_TEMPERATURE must be a number, got {raw!r}."
        ) from exc


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

    llm = ChatGroq(
        model=model_name,
        api_key=api_key,
        temperature=_groq_temperature(),
    )
    return create_react_agent(model=llm, tools=tools, prompt=SYSTEM_PROMPT)


def _sanitize_assistant_content(content: str) -> str:
    """Remove hallucinated text-based tool syntax from replayed assistant turns."""
    if not content:
        return content
    cleaned = _MALFORMED_TOOL_CALL_PATTERN.sub("", content).strip()
    if cleaned:
        return cleaned
    return "[Previous assistant tool-call output omitted due to invalid format.]"


def _contains_malformed_tool_syntax(content: str | None) -> bool:
    return bool(content and _MALFORMED_TOOL_CALL_PATTERN.search(content))


def _is_tool_use_failure(exc: Exception) -> bool:
    message = str(exc).lower()
    return "tool_use_failed" in message or "failed to call a function" in message


def _history_to_messages(history: list[dict]) -> list:
    trimmed = history[-MAX_HISTORY_MESSAGES:] if history else []
    messages = []
    for item in trimmed:
        role = item.get("role", "")
        content = item.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=_sanitize_assistant_content(content)))
    return messages


async def run_agent(
    agent, message: str, history: list[dict] | None = None
) -> str:
    """Invoke the agent with a user message and optional chat history."""
    messages = _history_to_messages(history or [])
    messages.append(HumanMessage(content=message))

    last_error: Exception | None = None
    for attempt in range(MAX_AGENT_ATTEMPTS):
        try:
            result = await agent.ainvoke({"messages": messages})
            final_message = result["messages"][-1]
            content = final_message.content or ""
            if _contains_malformed_tool_syntax(content):
                if attempt < MAX_AGENT_ATTEMPTS - 1:
                    messages.append(HumanMessage(content=_TOOL_RETRY_REMINDER))
                    continue
                raise AgentInvocationError(
                    "The model returned invalid text-based tool syntax instead of "
                    "using native tool calling."
                )
            return content
        except AgentInvocationError:
            raise
        except Exception as exc:
            last_error = exc
            if _is_tool_use_failure(exc) and attempt < MAX_AGENT_ATTEMPTS - 1:
                messages.append(HumanMessage(content=_TOOL_RETRY_REMINDER))
                continue
            raise

    raise AgentInvocationError(
        "Weather agent failed after retries due to tool-calling errors."
    ) from last_error
