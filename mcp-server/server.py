import os

import uvicorn
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse

import tools

load_dotenv()


def _resolve_bind() -> tuple[str, int]:
    """Render injects PORT; local default stays loopback."""
    port = int(os.getenv("PORT") or os.getenv("MCP_PORT", "8000"))
    host = os.getenv("MCP_HOST", "0.0.0.0" if os.getenv("PORT") else "127.0.0.1")
    return host, port


def _transport_security(host: str) -> TransportSecuritySettings | None:
    """
    MCP SDK auto-enables DNS rebinding protection when host is localhost,
    allowing only 127.0.0.1/localhost. That rejects PaaS Host headers (421).

    - MCP_ALLOWED_HOSTS: comma-separated public hostnames (recommended in prod)
    - Cloud bind (0.0.0.0 / PORT set): disable localhost-only guard
    - Localhost: leave SDK defaults (None)
    """
    raw = os.getenv("MCP_ALLOWED_HOSTS", "").strip()
    if raw:
        hosts: list[str] = []
        for item in raw.split(","):
            name = item.strip()
            if not name:
                continue
            hosts.append(name if ":" in name else f"{name}:*")
        hosts.extend(["127.0.0.1:*", "localhost:*"])
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
        )

    if host in ("0.0.0.0", "::") or os.getenv("PORT"):
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)

    return None


class _HealthASGI:
    """Serve GET/HEAD /health with 200 before forwarding to the MCP Starlette app.

    Relies on wrapping the ASGI app so Render health checks work even when the
    installed mcp package does not wire @custom_route into streamable HTTP.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path", "").rstrip("/") == "/health":
            if scope.get("method") in ("GET", "HEAD"):
                await JSONResponse({"status": "ok"})(scope, receive, send)
                return
        await self.app(scope, receive, send)


_bind_host, _bind_port = _resolve_bind()

# Pass host at construction time so transport security matches the real bind.
mcp = FastMCP(
    "weather",
    host=_bind_host,
    port=_bind_port,
    transport_security=_transport_security(_bind_host),
)


@mcp.tool()
async def geocode_city(city: str) -> dict:
    """Resolve a city name to latitude and longitude coordinates."""
    return await tools.geocode_city(city)


@mcp.tool()
async def get_current_weather(city: str) -> dict:
    """Get current weather conditions for a city."""
    return await tools.get_current_weather(city)


@mcp.tool()
async def get_forecast(city: str, days: int = 3) -> dict:
    """Get a daily weather forecast for a city (1-5 days)."""
    return await tools.get_forecast(city, days=days)


if __name__ == "__main__":
    mcp.settings.host = _bind_host
    mcp.settings.port = _bind_port
    asgi_app = _HealthASGI(mcp.streamable_http_app())
    uvicorn.run(
        asgi_app,
        host=_bind_host,
        port=_bind_port,
        log_level="info",
    )
