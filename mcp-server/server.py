import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

import weather_client

load_dotenv()

mcp = FastMCP("weather")


@mcp.tool()
async def geocode_city(city: str) -> dict:
    """Resolve a city name to latitude and longitude coordinates."""
    return await weather_client.geocode(city)


@mcp.tool()
async def get_current_weather(city: str) -> dict:
    """Get current weather conditions for a city."""
    return await weather_client.current(city)


@mcp.tool()
async def get_forecast(city: str, days: int = 3) -> dict:
    """Get a daily weather forecast for a city (1-5 days)."""
    return await weather_client.forecast(city, days=days)


if __name__ == "__main__":
    mcp.settings.host = os.getenv("MCP_HOST", "127.0.0.1")
    mcp.settings.port = int(os.getenv("MCP_PORT", "8000"))
    mcp.run(transport="streamable-http")
