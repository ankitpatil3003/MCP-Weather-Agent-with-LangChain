import asyncio
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

import weather_client

MAX_LOCATION_LENGTH = 100
MAX_CALLS_PER_MINUTE = 10
WINDOW_SECONDS = 60.0
REQUEST_TIMEOUT_SECONDS = 5.0


class _TokenBucket:
    def __init__(self, capacity: int, refill_seconds: float) -> None:
        self._capacity = capacity
        self._refill_seconds = refill_seconds
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()

    def consume(self) -> bool:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now
        self._tokens = min(
            self._capacity,
            self._tokens + elapsed * (self._capacity / self._refill_seconds),
        )
        if self._tokens < 1:
            return False
        self._tokens -= 1
        return True


_buckets: dict[str, _TokenBucket] = defaultdict(
    lambda: _TokenBucket(MAX_CALLS_PER_MINUTE, WINDOW_SECONDS)
)


def _error(message: str) -> dict[str, Any]:
    return {"error": message}


def _validate_location(location: str) -> dict[str, Any] | None:
    if len(location) > MAX_LOCATION_LENGTH:
        return _error(
            f"Location string must be {MAX_LOCATION_LENGTH} characters or fewer"
        )
    return None


def _check_rate_limit(tool_name: str) -> dict[str, Any] | None:
    if not _buckets[tool_name].consume():
        return _error(
            f"Rate limit exceeded: maximum {MAX_CALLS_PER_MINUTE} calls "
            f"per minute for this tool"
        )
    return None


async def _call_with_retry(
    request: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    last_timeout = False
    for attempt in range(2):
        try:
            return await asyncio.wait_for(request(), timeout=REQUEST_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            last_timeout = True
            if attempt == 1:
                break
    if last_timeout:
        return _error(
            f"OpenWeatherMap request timed out after {REQUEST_TIMEOUT_SECONDS} seconds"
        )
    return _error("OpenWeatherMap request failed after retry")


async def geocode_city(city: str) -> dict[str, Any]:
    if err := _check_rate_limit("geocode_city"):
        return err
    if err := _validate_location(city):
        return err
    return await _call_with_retry(lambda: weather_client.geocode(city))


async def get_current_weather(city: str) -> dict[str, Any]:
    if err := _check_rate_limit("get_current_weather"):
        return err
    if err := _validate_location(city):
        return err
    return await _call_with_retry(lambda: weather_client.current(city))


async def get_forecast(city: str, days: int = 3) -> dict[str, Any]:
    if err := _check_rate_limit("get_forecast"):
        return err
    if err := _validate_location(city):
        return err
    return await _call_with_retry(lambda: weather_client.forecast(city, days=days))
