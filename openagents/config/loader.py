"""Config loader entrypoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import AppConfig
from .validator import validate_config
from ..errors.exceptions import ConfigError


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Config file does not exist: {config_path}")
    if not config_path.is_file():
        raise ConfigError(f"Config path is not a file: {config_path}")

    try:
        raw_text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Failed to read config file: {config_path}") from exc

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in config file: {config_path}") from exc

    return load_config_dict(payload)


def load_config_dict(payload: dict[str, Any]) -> AppConfig:
    try:
        config = AppConfig.from_dict(payload)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
    validate_config(config)
    return config

