import os
from collections import defaultdict
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

GEO_BASE = "https://api.openweathermap.org/geo/1.0"
WEATHER_BASE = "https://api.openweathermap.org/data/2.5"
REQUEST_TIMEOUT = 30.0


def _api_key() -> str | None:
    key = os.getenv("OPENWEATHER_API_KEY")
    if key and key.strip():
        return key.strip()
    return None


def _error(message: str) -> dict[str, Any]:
    return {"error": message}


async def geocode(city: str) -> dict[str, Any]:
    api_key = _api_key()
    if not api_key:
        return _error("OPENWEATHER_API_KEY environment variable is not set")

    query = city.strip()
    if not query:
        return _error("City name is required")

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{GEO_BASE}/direct",
                params={"q": query, "limit": 1, "appid": api_key},
            )
            response.raise_for_status()
            results = response.json()
    except httpx.HTTPStatusError as exc:
        return _error(f"Geocoding request failed: HTTP {exc.response.status_code}")
    except httpx.RequestError as exc:
        return _error(f"Geocoding request failed: {exc}")

    if not results:
        return _error(f"City not found: {query}")

    location = results[0]
    return {
        "name": location.get("name"),
        "lat": location.get("lat"),
        "lon": location.get("lon"),
        "country": location.get("country"),
        "state": location.get("state"),
    }


async def current(city: str) -> dict[str, Any]:
    location = await geocode(city)
    if "error" in location:
        return location

    api_key = _api_key()
    if not api_key:
        return _error("OPENWEATHER_API_KEY environment variable is not set")

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{WEATHER_BASE}/weather",
                params={
                    "lat": location["lat"],
                    "lon": location["lon"],
                    "units": "metric",
                    "appid": api_key,
                },
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        return _error(f"Current weather request failed: HTTP {exc.response.status_code}")
    except httpx.RequestError as exc:
        return _error(f"Current weather request failed: {exc}")

    weather = data.get("weather", [{}])[0]
    main = data.get("main", {})
    wind = data.get("wind", {})

    return {
        "city": data.get("name", location.get("name")),
        "country": location.get("country"),
        "coordinates": {"lat": location["lat"], "lon": location["lon"]},
        "temperature_c": main.get("temp"),
        "feels_like_c": main.get("feels_like"),
        "humidity": main.get("humidity"),
        "description": weather.get("description"),
        "wind_speed_m_s": wind.get("speed"),
    }


def _summarize_forecast(entries: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for entry in entries:
        dt_txt = entry.get("dt_txt", "")
        if not dt_txt:
            continue
        by_date[dt_txt.split(" ")[0]].append(entry)

    summaries: list[dict[str, Any]] = []
    for date in sorted(by_date.keys())[:days]:
        day_entries = by_date[date]
        temps = [
            entry["main"]["temp"]
            for entry in day_entries
            if entry.get("main", {}).get("temp") is not None
        ]
        humidity = [
            entry["main"]["humidity"]
            for entry in day_entries
            if entry.get("main", {}).get("humidity") is not None
        ]
        wind_speeds = [
            entry["wind"]["speed"]
            for entry in day_entries
            if entry.get("wind", {}).get("speed") is not None
        ]
        pop_values = [entry.get("pop", 0) for entry in day_entries]
        midday = next(
            (entry for entry in day_entries if "12:00:00" in entry.get("dt_txt", "")),
            day_entries[len(day_entries) // 2],
        )

        summaries.append(
            {
                "date": date,
                "temp_min_c": min(temps) if temps else None,
                "temp_max_c": max(temps) if temps else None,
                "avg_humidity": round(sum(humidity) / len(humidity)) if humidity else None,
                "description": midday.get("weather", [{}])[0].get("description"),
                "pop_max": max(pop_values) if pop_values else None,
                "wind_speed_m_s": max(wind_speeds) if wind_speeds else None,
                "samples": len(day_entries),
            }
        )

    return summaries


async def forecast(city: str, days: int = 3) -> dict[str, Any]:
    location = await geocode(city)
    if "error" in location:
        return location

    if days < 1 or days > 5:
        return _error("Days must be between 1 and 5")

    api_key = _api_key()
    if not api_key:
        return _error("OPENWEATHER_API_KEY environment variable is not set")

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{WEATHER_BASE}/forecast",
                params={
                    "lat": location["lat"],
                    "lon": location["lon"],
                    "units": "metric",
                    "appid": api_key,
                },
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        return _error(f"Forecast request failed: HTTP {exc.response.status_code}")
    except httpx.RequestError as exc:
        return _error(f"Forecast request failed: {exc}")

    city_info = data.get("city", {})
    return {
        "city": city_info.get("name", location.get("name")),
        "country": location.get("country"),
        "coordinates": {"lat": location["lat"], "lon": location["lon"]},
        "days": days,
        "forecast": _summarize_forecast(data.get("list", []), days),
    }
