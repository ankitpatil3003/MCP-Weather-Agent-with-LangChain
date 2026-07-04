#!/usr/bin/env python3
"""Verify safety constraints in mcp-server/tools.py without live server or API keys."""

import asyncio
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "mcp-server"))

# Stub weather_client so tools imports without httpx/network.
_weather_stub = ModuleType("weather_client")
_weather_stub.geocode = AsyncMock()
_weather_stub.current = AsyncMock()
_weather_stub.forecast = AsyncMock()
sys.modules["weather_client"] = _weather_stub

import tools

tools.weather_client = _weather_stub


def reset_rate_limits() -> None:
    tools._buckets.clear()


async def test_normal_call_succeeds() -> None:
    reset_rate_limits()
    expected = {"city": "London", "lat": 51.5, "lon": -0.1}
    with patch.object(tools.weather_client, "geocode", new_callable=AsyncMock) as mock_geocode:
        mock_geocode.return_value = expected
        result = await tools.geocode_city("London")
        if "error" in result:
            raise AssertionError(f"Expected success, got error: {result['error']}")
        if result != expected:
            raise AssertionError(f"Unexpected result: {result}")
        mock_geocode.assert_called_once_with("London")


async def test_101_char_location_rejected() -> None:
    reset_rate_limits()
    long_location = "a" * 101
    with patch.object(tools.weather_client, "geocode", new_callable=AsyncMock) as mock_geocode:
        result = await tools.geocode_city(long_location)
        if "error" not in result:
            raise AssertionError(f"Expected error, got: {result}")
        if "100 characters or fewer" not in result["error"]:
            raise AssertionError(f"Wrong error message: {result['error']}")
        mock_geocode.assert_not_called()


async def test_rate_limit_after_10_calls() -> None:
    reset_rate_limits()
    success = {"city": "London", "lat": 51.5, "lon": -0.1}
    with patch.object(tools.weather_client, "geocode", new_callable=AsyncMock) as mock_geocode:
        mock_geocode.return_value = success
        for i in range(10):
            result = await tools.geocode_city("London")
            if "error" in result:
                raise AssertionError(f"Call {i + 1} failed unexpectedly: {result['error']}")
        result = await tools.geocode_city("London")
        if "error" not in result:
            raise AssertionError("11th call should have been rate limited")
        if "Rate limit exceeded" not in result["error"]:
            raise AssertionError(f"Wrong error message: {result['error']}")


async def test_timeout_retry() -> None:
    reset_rate_limits()

    async def slow_geocode(_city: str) -> dict:
        await asyncio.sleep(10)

    with patch.object(tools.weather_client, "geocode", side_effect=slow_geocode):
        result = await tools.geocode_city("London")
        if "error" not in result:
            raise AssertionError(f"Expected timeout error, got: {result}")
        if "timed out after 5" not in result["error"]:
            raise AssertionError(f"Wrong error message: {result['error']}")


TESTS = [
    ("Normal call succeeds", test_normal_call_succeeds),
    ("101-char location rejected", test_101_char_location_rejected),
    ("Rate limit after 10 calls", test_rate_limit_after_10_calls),
    ("Timeout + retry", test_timeout_retry),
]


def main() -> None:
    failed = 0
    for name, test_fn in TESTS:
        try:
            asyncio.run(test_fn())
            print(f"PASS: {name}")
        except Exception as exc:
            print(f"FAIL: {name} — {exc}")
            failed += 1

    if failed:
        sys.exit(1)
    print(f"\nAll {len(TESTS)} tests passed.")


if __name__ == "__main__":
    main()
