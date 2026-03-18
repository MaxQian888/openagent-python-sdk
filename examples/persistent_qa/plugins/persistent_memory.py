"""Custom persistent memory plugin - stores conversation history to JSON file."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from openagents.interfaces.capabilities import MEMORY_INJECT, MEMORY_WRITEBACK
from openagents.interfaces.memory import MemoryPlugin


class PersistentMemory(MemoryPlugin):
    """Persistent memory that stores conversation history to JSON file.

    Features:
    - Stores full conversation history to local JSON file
    - Supports semantic search via keyword matching
    - Fallback to recent history when search fails
    - Automatic file creation and management
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(
            config=config or {},
            capabilities={MEMORY_INJECT, MEMORY_WRITEBACK},
        )
        # Storage directory for persistence
        self._storage_dir = self.config.get("storage_dir", ".agent_memory")
        self._max_items = self.config.get("max_items", 100)
        self._ensure_storage_dir()

    def _ensure_storage_dir(self) -> None:
        """Ensure storage directory exists."""
        Path(self._storage_dir).mkdir(parents=True, exist_ok=True)

    def _get_storage_path(self, session_id: str) -> Path:
        """Get storage file path for a session."""
        # Sanitize session_id for file name
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
        return Path(self._storage_dir) / f"memory_{safe_id}.json"

    def _load_history(self, session_id: str) -> list[dict[str, Any]]:
        """Load history from file."""
        path = self._get_storage_path(session_id)
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError):
            return []

    def _save_history(self, session_id: str, history: list[dict[str, Any]]) -> None:
        """Save history to file."""
        path = self._get_storage_path(session_id)
        # Trim to max_items
        history = history[-self._max_items:] if len(history) > self._max_items else history
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def _search_history(self, query: str, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Search history by keyword matching."""
        query_lower = query.lower()
        results = []
        for item in reversed(history):
            # Search in input and output
            input_text = item.get("input", "").lower()
            output_text = str(item.get("output", "")).lower()
            if query_lower in input_text or query_lower in output_text:
                results.append(item)
        return results[:5]  # Return top 5 matches

    async def inject(self, context: Any) -> None:
        """Inject memory into context.

        Fallback chain:
        1. Try keyword search in persistent storage
        2. If no results, load recent history
        3. If file doesn't exist, use empty list
        """
        session_id = context.session_id

        # First, try to search for related context
        query = context.input_text
        history = self._load_history(session_id)

        if history:
            # Try semantic search
            relevant = self._search_history(query, history)

            if relevant:
                # Found relevant history
                context.memory_view["history"] = relevant
                context.memory_view["memory_source"] = "search"
                context.memory_view["search_query"] = query
                return

        # Fallback: use recent history
        recent = history[-5:] if history else []
        context.memory_view["history"] = recent
        context.memory_view["memory_source"] = "recent"
        context.memory_view["search_query"] = query if history else None

    async def writeback(self, context: Any) -> None:
        """Write back current interaction to persistent storage."""
        session_id = context.session_id

        # Load existing history
        history = self._load_history(session_id)

        # Create new record
        record: dict[str, Any] = {
            "input": context.input_text,
            "tool_results": [tr.get("result", {}) for tr in context.tool_results],
        }

        if "_runtime_last_output" in context.state:
            record["output"] = context.state["_runtime_last_output"]

        # Add timestamp
        from datetime import datetime, timezone
        record["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Append and save
        history.append(record)
        self._save_history(session_id, history)

        # Update memory view
        context.memory_view["history"] = history[-5:]
        context.memory_view["saved"] = True

    def describe(self) -> dict[str, Any]:
        """Return tool description for LLM."""
        return {
            "name": "PersistentMemory",
            "description": "Persistent memory that stores conversation history to JSON files with keyword search capability",
            "parameters": {
                "type": "object",
                "properties": {
                    "storage_dir": {"type": "string", "description": "Directory to store memory files"},
                    "max_items": {"type": "integer", "description": "Maximum history items to store"},
                },
            },
        }
