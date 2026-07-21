# Deploy Weather MCP to Render

## Why this service exists

Trippi-AI calls this MCP over streamable HTTP. Deploy it before the Trippi-AI API so `MCP_SERVER_URL` points at a public endpoint.

## Render (recommended)

1. Push `mcp-server` Docker support (`Dockerfile`, root `render.yaml`).
2. In Render: New → Blueprint, or Web Service from `mcp-server` with Docker runtime.
3. Set secret `OPENWEATHER_API_KEY`.
4. Set `MCP_HOST=0.0.0.0`. Render injects `PORT`; `server.py` honors `PORT`.
5. Optional: set `MCP_ALLOWED_HOSTS=weather-mcp-xxxx.onrender.com` to keep DNS
   rebinding protection with an explicit allowlist. If unset on cloud (`PORT` /
   `0.0.0.0`), the server disables the localhost-only Host guard so Render’s
   public Host header is accepted (avoids `421 Invalid Host header`).
6. After deploy, public URL looks like `https://weather-mcp.onrender.com/mcp`.
7. Smoke (PowerShell: use `curl.exe`):

```bash
curl.exe -i https://YOUR_SERVICE.onrender.com/mcp
```

A non-connection-failure response (including MCP protocol **406** on plain GET)
means the process is up. **421** means Host-header protection is rejecting the
Render hostname — redeploy with the fixed `server.py` or set `MCP_ALLOWED_HOSTS`.

Health checks must use **`/health`** (returns 200). Do **not** use `/mcp` as
`healthCheckPath` — Render expects 2xx and `/mcp` returns 406, which leaves
deploys stuck in “Deploying”.

8. Put that base MCP URL into Trippi-AI as `MCP_SERVER_URL`.

## Free tier notes

Render free services sleep after idle time. Trippi-AI MCP client retries on cold start. First forecast after sleep may take 30 to 60 seconds.

## Local alternative

```bash
cd mcp-server
python server.py
# MCP_SERVER_URL=http://127.0.0.1:8000/mcp
```
