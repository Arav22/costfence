"""Configuration loader — reads from ~/.costfence/config.yaml or env vars."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_PATH = Path.home() / ".costfence" / "config.yaml"

DEFAULT_CONFIG = {
    "budgets": {
        "per_session": 5.0,
        "per_hour": 10.0,
        "per_day": 50.0,
    },
    "targets": {
        "openai": "https://api.openai.com",
        "anthropic": "https://api.anthropic.com",
    },
    "port": 8990,
    "host": "127.0.0.1",
}


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or Path(os.environ.get("COSTFENCE_CONFIG", str(DEFAULT_CONFIG_PATH)))
    config = dict(DEFAULT_CONFIG)

    if config_path.exists():
        with open(config_path) as f:
            user_config = yaml.safe_load(f) or {}
        _deep_merge(config, user_config)

    if env_session := os.environ.get("COSTFENCE_SESSION_BUDGET"):
        config.setdefault("budgets", {})["per_session"] = float(env_session)
    if env_hour := os.environ.get("COSTFENCE_HOURLY_BUDGET"):
        config.setdefault("budgets", {})["per_hour"] = float(env_hour)
    if env_day := os.environ.get("COSTFENCE_DAILY_BUDGET"):
        config.setdefault("budgets", {})["per_day"] = float(env_day)
    if env_project := os.environ.get("COSTFENCE_PROJECT"):
        config["project"] = env_project
    if env_port := os.environ.get("COSTFENCE_PORT"):
        config["port"] = int(env_port)

    return config


def create_default_config() -> Path:
    DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DEFAULT_CONFIG_PATH.exists():
        with open(DEFAULT_CONFIG_PATH, "w") as f:
            yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, sort_keys=False)
    return DEFAULT_CONFIG_PATH


def _deep_merge(base: dict, override: dict) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
