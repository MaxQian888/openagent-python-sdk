"""Custom weather tool with fallback mechanism.

Features:
- Primary: Real weather API call
- Fallback: Cached results or error message
- Retry support
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any

from openagents.interfaces.capabilities import TOOL_INVOKE
from openagents.interfaces.tool import ToolPlugin, RetryableToolError, PermanentToolError


class WeatherTool(ToolPlugin):
    """Weather query tool with fallback support.

    Fallback chain:
    1. Try to fetch real weather data
    2. If fails with RetryableToolError -> return cached/demo data
    3. If fails with PermanentToolError -> return helpful error
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(
            config=config or {},
            capabilities={TOOL_INVOKE},
        )
        self.name = "weather"
        self.description = "Get current weather information for a city"
        self._api_key = self.config.get("api_key")
        self._use_cache = self.config.get("use_cache", True)
        self._cache: dict[str, Any] = {}

    def schema(self) -> dict[str, Any]:
        """Return JSON Schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name (e.g., Beijing, Shanghai, New York)",
                },
                "units": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature units",
                    "default": "celsius",
                },
            },
            "required": ["city"],
        }

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        """Fetch weather data."""
        city = params.get("city", "")
        units = params.get("units", "celsius")

        if not city:
            raise PermanentToolError("City parameter is required", tool_name="weather")

        # Check cache first
        cache_key = f"{city}:{units}"
        if self._use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            # Cache valid for 30 minutes
            if datetime.now(timezone.utc) - cached.get("cached_at", datetime.min) < timedelta(minutes=30):
                cached["from_cache"] = True
                return cached

        # Try to fetch real data (simulated - replace with real API in production)
        try:
            # Simulate API call - in production, use real weather API
            # Example: OpenWeatherMap, WeatherAPI, etc.
            weather_data = await self._fetch_weather(city, units)

            # Cache the result
            weather_data["cached_at"] = datetime.now(timezone.utc)
            self._cache[cache_key] = weather_data

            return weather_data

        except Exception as exc:
            # Check if it's a retryable error
            if isinstance(exc, RetryableToolError):
                raise
            # For other errors, wrap as retryable
            raise RetryableToolError(f"Weather API unavailable: {exc}", tool_name="weather")

    async def _fetch_weather(self, city: str, units: str) -> dict[str, Any]:
        """Fetch weather from API (simulated)."""
        # Simulate network delay
        await asyncio.sleep(0.1)

        # In production, replace with real API call:
        # import httpx
        # async with httpx.AsyncClient() as client:
        #     response = await client.get(
        #         f"https://api.weather.com/v1/current",
        #         params={"city": city, "units": units, "api_key": self._api_key}
        #     )
        #     return response.json()

        # Simulated response
        conditions = ["sunny", "cloudy", "rainy", "partly cloudy", "clear"]
        temps = {
            "celsius": {"Beijing": 15, "Shanghai": 22, "New York": 18, "London": 12, "Tokyo": 20},
            "fahrenheit": {"Beijing": 59, "Shanghai": 72, "New York": 64, "London": 54, "Tokyo": 68},
        }

        unit_key = "celsius" if units == "celsius" else "fahrenheit"
        temp = temps[unit_key].get(city, 20 if units == "celsius" else 68)

        return {
            "city": city,
            "temperature": temp,
            "units": units,
            "condition": conditions[hash(city) % len(conditions)],
            "humidity": 65,
            "wind_speed": 10,
            "from_cache": False,
        }

    async def fallback(self, error: Exception, params: dict[str, Any], context: Any) -> Any:
        """Fallback handler when invoke fails."""
        city = params.get("city", "unknown")

        # Check if we have cached data
        cache_key = f"{city}:{params.get('units', 'celsius')}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            cached["from_fallback"] = True
            cached["fallback_reason"] = str(error)
            return cached

        # Return demo data as last resort
        return {
            "city": city,
            "temperature": 20,
            "units": "celsius",
            "condition": "unknown (offline)",
            "humidity": 50,
            "wind_speed": 0,
            "from_fallback": True,
            "fallback_reason": f"API unavailable: {error}",
            "note": "This is cached/fallback data. Real-time data unavailable.",
        }


class SearchTool(ToolPlugin):
    """Web search tool with fallback to local knowledge base."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(
            config=config or {},
            capabilities={TOOL_INVOKE},
        )
        self.name = "search"
        self.description = "Search the web for information"

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results", "default": 5},
            },
            "required": ["query"],
        }

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        """Perform web search."""
        query = params.get("query", "")
        limit = params.get("limit", 5)

        if not query:
            raise PermanentToolError("Query parameter is required", tool_name="search")

        # Try real search (simulated)
        try:
            results = await self._search_web(query, limit)
            return results
        except Exception as exc:
            raise RetryableToolError(f"Search failed: {exc}", tool_name="search")

    async def _search_web(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Perform actual web search."""
        # Simulate search - replace with real search API
        await asyncio.sleep(0.2)

        # Demo results
        return [
            {
                "title": f"Result {i+1} for {query}",
                "url": f"https://example.com/result{i+1}",
                "snippet": f"This is a search result snippet for '{query}'. It contains relevant information about the topic.",
            }
            for i in range(limit)
        ]

    async def fallback(self, error: Exception, params: dict[str, Any], context: Any) -> Any:
        """Fallback when search fails."""
        query = params.get("query", "")

        # Return local knowledge as fallback
        return [
            {
                "title": "Local Knowledge Base",
                "url": "local://knowledge",
                "snippet": f"Search service unavailable. Query was: {query}. Please try again later or reformulate your question.",
                "from_fallback": True,
            }
        ]
