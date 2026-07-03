# MCP Weather Agent with LangChain

An agent-driven weather web application that wraps the OpenWeatherMap REST API behind a **Model Context Protocol (MCP)** server, uses a **LangChain / LangGraph** agent with **Groq** for tool calling, and exposes a **Streamlit** chat UI.

**Repository:** [github.com/ankitpatil3003/MCP-Weather-Agent-with-LangChain](https://github.com/ankitpatil3003/MCP-Weather-Agent-with-LangChain)

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

## Repository structure

```
MCP-Weather-Agent-with-LangChain/
├── mcp-server/           # MCP server wrapper (FastMCP + OpenWeatherMap)
│   ├── server.py
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
