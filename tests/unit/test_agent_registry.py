import pytest

from services.agent_gateway.app.core.errors import ApiError
from services.agent_gateway.app.services.agent_registry import get_agent_config


def test_get_agent_config_returns_maxima() -> None:
    assert get_agent_config("maxima").agent_id == "maxima"


def test_get_agent_config_rejects_unknown_agent() -> None:
    with pytest.raises(ApiError) as exc_info:
        get_agent_config("unknown-agent")
    assert exc_info.value.code == "unknown_agent"

