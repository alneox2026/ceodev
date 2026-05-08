"""Server-side agent registry loading and lookup."""

from __future__ import annotations

from functools import lru_cache

import yaml

from common.ids import validate_agent_id
from common.schemas import AgentConfig
from services.agent_gateway.app.core.config import get_settings
from services.agent_gateway.app.core.errors import ApiError


@lru_cache(maxsize=1)
def load_registry() -> dict[str, AgentConfig]:
    settings = get_settings()
    with settings.agent_registry_path.open("r", encoding="utf-8") as handle:
        parsed = yaml.safe_load(handle) or {}

    agents = parsed.get("agents")
    if not isinstance(agents, dict) or not agents:
        raise RuntimeError("Agent registry must contain a non-empty 'agents' mapping.")

    registry: dict[str, AgentConfig] = {}
    for raw_agent_id, config in agents.items():
        if not isinstance(config, dict):
            raise RuntimeError(f"Agent config for '{raw_agent_id}' must be an object.")
        agent_config = AgentConfig(**config)
        registry[agent_config.agent_id] = agent_config
    return registry


def get_agent_config(agent_id: str) -> AgentConfig:
    cleaned_agent_id = validate_agent_id(agent_id)
    registry = load_registry()
    agent_config = registry.get(cleaned_agent_id)
    if agent_config is None:
        raise ApiError(
            404,
            "unknown_agent",
            "The requested agent is not registered in this middleware.",
            {"agent_id": cleaned_agent_id},
        )
    return agent_config

