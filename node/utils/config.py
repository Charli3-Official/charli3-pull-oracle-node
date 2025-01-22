"""Configuration setup for node backend."""

import logging
import os
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)


def load_yaml_config(path: str | Path) -> Dict[str, Any]:
    """Load YAML configuration with support for includes and environment variables."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if "include" in config:
        included_path = path.parent / config["include"]
        with included_path.open("r", encoding="utf-8") as f:
            included_config = yaml.safe_load(f)
            config = {**included_config, **config}
            config.pop("include")

    return resolve_env_vars(config)


def resolve_env_vars(config: Any) -> Any:
    """Resolve environment variables in configuration values."""
    if isinstance(config, dict):
        return {k: resolve_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [resolve_env_vars(v) for v in config]
    elif isinstance(config, str) and config.startswith("<%=") and config.endswith("%>"):
        var_name = config[4:-2].strip().lstrip("@")
        return os.getenv(var_name, config)
    return config
