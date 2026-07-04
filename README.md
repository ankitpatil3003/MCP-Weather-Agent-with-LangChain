# MCP Weather Agent with LangChain

An agent-driven weather web application that wraps the OpenWeatherMap REST API behind a **Model Context Protocol (MCP)** server, uses a **LangChain / LangGraph** agent with **Groq** for tool calling, and exposes a **Streamlit** chat UI.

**Repository:** [github.com/ankitpatil3003/MCP-Weather-Agent-with-LangChain](https://github.com/ankitpatil3003/MCP-Weather-Agent-with-LangChain)

**Built with [Cursor](https://cursor.com)** — this project was developed using Cursor as the agentic IDE (not Replit, v0, or Bolt). See [Development with Cursor](#development-with-cursor) for the workflow and PR history.

## Architecture

```
User
  │
  ▼
Streamlit UI (frontend/)          :8501
  │  POST /chat
  ▼
FastAPI Agent Backend (agent-backend/)   :8001
  │  LangGraph ReAct agent + ChatGroq
  │  MCP client (streamable HTTP)
  ▼
MCP Weather Server (mcp-server/)         :8000
  │  geocode_city, get_current_weather, get_forecast
  ▼
OpenWeatherMap API
```

| Service | Role | Default URL |
|---------|------|-------------|
| **mcp-server** | MCP wrapper for OpenWeatherMap | `http://127.0.0.1:8000/mcp` |
| **agent-backend** | LLM agent with MCP tool calling | `http://127.0.0.1:8001` |
| **frontend** | Streamlit chat interface | `http://localhost:8501` |

## Security design

API keys are scoped to the service that needs them. No key is shared across tiers or exposed to the browser.

| Secret | Loaded in | Used for | Not accessible from |
|--------|-----------|----------|---------------------|
| `OPENWEATHER_API_KEY` | `mcp-server/.env` | Outbound calls to OpenWeatherMap | Agent backend, Streamlit frontend |
| `GROQ_API_KEY` | `agent-backend/.env` | LLM inference (ChatGroq) | MCP server, Streamlit frontend |

**Trust boundaries**

- The **frontend** only talks to the agent backend (`POST /chat`). It never holds weather or LLM keys.
- The **agent backend** calls MCP tools over streamable HTTP. It never calls OpenWeatherMap directly and never receives the weather API key.
- The **MCP server** is the only component that holds `OPENWEATHER_API_KEY`. Tool calls return structured JSON (weather data or error messages), not raw API credentials.

**Abuse protection** — [`mcp-server/tools.py`](mcp-server/tools.py) sits in front of every outbound weather request: rate limiting (10 calls/minute per tool), location length validation, and timeout/retry. This limits accidental or excessive use of the weather API key without changing `weather_client.py`.

For local development, all three services bind to `127.0.0.1` by default. Hosting is not required for this project; if deployed, add authentication in front of `/chat` and the MCP endpoint.

## Development with Cursor

This repository was built end-to-end in **Cursor**, using the agent for architecture design, incremental implementation, live E2E verification, and GitHub PR delivery.

**Workflow**

1. **Design** — Brainstorm architecture (MCP wrapper, Groq agent, Streamlit UI) before coding
2. **Phased build** — Scaffold → MCP server → agent backend → frontend → README → safety limits
3. **Feature branches** — Each layer on `feat/*`, merged via Pull Request (never direct push to `develop`/`main`)
4. **Verification** — Live E2E checks after each layer (MCP tools, agent `/chat`, safety constraints)

**Merged PRs (audit trail)**

| PR | Description |
|----|-------------|
| [#1](https://github.com/ankitpatil3003/MCP-Weather-Agent-with-LangChain/pull/1) | LangChain agent backend (Groq + MCP) |
| [#3](https://github.com/ankitpatil3003/MCP-Weather-Agent-with-LangChain/pull/3) | Streamlit chat UI |
| [#5](https://github.com/ankitpatil3003/MCP-Weather-Agent-with-LangChain/pull/5) | README and setup documentation |
| [#7](https://github.com/ankitpatil3003/MCP-Weather-Agent-with-LangChain/pull/7) | MCP tool safety limits (`tools.py`) |

Full history: [Pull requests](https://github.com/ankitpatil3003/MCP-Weather-Agent-with-LangChain/pulls?q=is%3Apr+is%3Amerged)

## Repository structure

```
MCP-Weather-Agent-with-LangChain/
├── mcp-server/           # MCP server wrapper (FastMCP + OpenWeatherMap)
│   ├── server.py
│   ├── tools.py          # Safety layer (rate limits, validation, retry)
│   ├── weather_client.py
│   ├── requirements.txt
│   └── .env.example
├── agent-backend/        # LangChain agent backend (FastAPI + Groq)
│   ├── main.py
│   ├── agent.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/             # Streamlit web UI
│   ├── app.py
│   ├── requirements.txt
│   └── .env.example
├── requirements.txt      # Installs all services (optional convenience)
└── README.md
```

## Prerequisites

- **Python 3.11+** (tested on 3.12)
- Free API keys:
  - [OpenWeatherMap](https://openweathermap.org/api) — weather data
  - [Groq](https://console.groq.com/) — LLM inference

## Dependencies

Install everything in one virtual environment from the repo root:

```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Or install per service:

| Path | Key packages |
|------|----------------|
| `mcp-server/requirements.txt` | `mcp`, `httpx`, `python-dotenv` |
| `agent-backend/requirements.txt` | `fastapi`, `uvicorn`, `langgraph`, `langchain`, `langchain-groq`, `langchain-mcp-adapters` |
| `frontend/requirements.txt` | `streamlit`, `httpx`, `python-dotenv` |

## API keys

### 1. OpenWeatherMap (third-party weather API)

1. Create a free account at [openweathermap.org](https://openweathermap.org/).
2. Open [API keys](https://home.openweathermap.org/api_keys) and generate a key.
3. New keys can take up to **2 hours** to activate. A `401` response usually means the key is missing or not yet active.

### 2. Groq (LLM)

1. Sign up at [console.groq.com](https://console.groq.com/).
2. Create an API key under **API Keys**.
3. Default model: `llama-3.3-70b-versatile` (supports tool calling).

## Environment configuration

Copy each `.env.example` to `.env` and add your keys:

```bash
# Windows (PowerShell)
copy mcp-server\.env.example mcp-server\.env
copy agent-backend\.env.example agent-backend\.env
copy frontend\.env.example frontend\.env

# macOS / Linux
cp mcp-server/.env.example mcp-server/.env
cp agent-backend/.env.example agent-backend/.env
cp frontend/.env.example frontend/.env
```

**Required variables**

| File | Variable | Description |
|------|----------|-------------|
| `mcp-server/.env` | `OPENWEATHER_API_KEY` | OpenWeatherMap API key |
| `agent-backend/.env` | `GROQ_API_KEY` | Groq API key |
| `agent-backend/.env` | `MCP_SERVER_URL` | Default `http://127.0.0.1:8000/mcp` |
| `frontend/.env` | `AGENT_BACKEND_URL` | Default `http://127.0.0.1:8001` |

Optional: `MCP_HOST`, `MCP_PORT`, `AGENT_HOST`, `AGENT_PORT`, `GROQ_MODEL`.

## Running the application

Start **three terminals** (with the virtual environment activated). Order matters: MCP server first, then agent backend, then frontend.

### Terminal 1 — MCP server

```bash
cd mcp-server
python server.py
```

Server listens at **`http://127.0.0.1:8000/mcp`** (streamable HTTP).

**MCP tools exposed**

| Tool | Description |
|------|-------------|
| `geocode_city(city)` | Resolve city name to coordinates |
| `get_current_weather(city)` | Current temperature, conditions, humidity, wind |
| `get_forecast(city, days=3)` | Daily forecast summary (1–5 days) |

**Safety limits** (`tools.py` — applied before every OpenWeatherMap call):

- In-memory rate limit: **10 calls/minute per tool**
- Location strings over **100 characters** are rejected
- Outbound API calls: **5-second timeout** with **one retry**

### Terminal 2 — Agent backend

```bash
cd agent-backend
python main.py
```

- Health: `GET http://127.0.0.1:8001/health`
- Chat: `POST http://127.0.0.1:8001/chat` with JSON `{"message": "...", "history": []}`

### Terminal 3 — Web application

```bash
cd frontend
streamlit run app.py
```

Open **`http://localhost:8501`** and ask questions such as:

- *What's the weather in Tokyo?*
- *Will it rain in London this weekend?*

## Prompt design

The agent uses a **two-layer prompt strategy**: a system prompt in the backend and tool descriptions on the MCP server.

### System prompt (`agent-backend/agent.py`)

A `SystemMessage` is passed to LangGraph’s `create_react_agent(..., prompt=SYSTEM_PROMPT)`. It is injected at the start of every ReAct loop so the model consistently:

- Calls MCP weather tools for facts — never invents temperatures or conditions
- Surfaces tool errors (JSON objects with an `"error"` field) instead of guessing
- Reports temperatures in **°C** with city and country when available
- Chooses `get_current_weather` vs `get_forecast` based on the user’s question
- Asks the user to clarify ambiguous city names (e.g. “Springfield”) before calling tools

Chat history from the frontend is appended after this system context on each `/chat` request.

### Tool descriptions (`mcp-server/server.py`)

Each MCP tool’s docstring is exposed to the LLM via `langchain-mcp-adapters`. These short descriptions guide **which tool to call**:

| Tool | Docstring role |
|------|----------------|
| `geocode_city` | Resolve a city to coordinates when location lookup is needed |
| `get_current_weather` | Current conditions — temperature, humidity, wind, description |
| `get_forecast` | Daily forecast summary; accepts `days` (1–5) |

The ReAct agent reads the user message, picks a tool from these descriptions, executes it over MCP, then synthesizes a natural-language reply.

### Edge cases handled

| Scenario | Behavior |
|----------|----------|
| Tool returns `{"error": "..."}` | System prompt instructs the agent to explain the error (rate limit, city not found, validation failure) |
| Ambiguous city | Agent asks for country or region before calling tools |
| Forecast vs current | System prompt maps question intent to `get_forecast` or `get_current_weather` |
| Safety validation (e.g. location > 100 chars) | `tools.py` rejects the request; agent relays the error message |

## Quick verification

**MCP health** (406 on a plain GET is normal for MCP):

```bash
curl http://127.0.0.1:8000/mcp
```

**Agent health:**

```bash
curl http://127.0.0.1:8001/health
```

**Agent chat:**

```bash
curl -X POST http://127.0.0.1:8001/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"What is the weather in London?\"}"
```

*(Use `\` line continuation on macOS/Linux.)*

## Troubleshooting

| Issue | Likely cause | Fix |
|-------|----------------|-----|
| OpenWeather `401` | Key invalid or not activated | Wait up to 2h after signup; regenerate key |
| `GROQ_API_KEY is not set` | Missing `agent-backend/.env` | Copy `.env.example` and set key |
| Cannot connect to backend (Streamlit) | Agent not running | Start `agent-backend/main.py` on port 8001 |
| MCP connection failed | MCP server not running | Start `mcp-server/server.py` first |
| `uuid_utils` / DLL blocked (Windows) | Application Control policy | Allow the venv package, use WSL/Linux, or run outside restricted policy |
| Groq `tool_use_failed` | Transient model tool format error | Retry the request; ensure MCP server is up before chatting |

## Branching workflow

- **`develop`** — integration branch for features
- **`main`** — production-ready releases
- Feature work merges via GitHub Pull Requests: `feat/*` → `develop` → `main`

## License

See repository license file (if present). API usage subject to [OpenWeatherMap](https://openweathermap.org/terms) and [Groq](https://groq.com/terms) terms.
