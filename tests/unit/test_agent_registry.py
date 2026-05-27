import pytest

from services.agent_gateway.app.core.config import get_settings
from services.agent_gateway.app.core.errors import ApiError
from services.agent_gateway.app.services.agent_registry import get_agent_config, load_registry


@pytest.fixture(autouse=True)
def clear_registry_cache():
    get_settings.cache_clear()
    load_registry.cache_clear()
    yield
    get_settings.cache_clear()
    load_registry.cache_clear()


def test_get_agent_config_returns_maxima() -> None:
    assert get_agent_config("maxima").agent_id == "maxima"


def test_get_agent_config_rejects_unknown_agent() -> None:
    with pytest.raises(ApiError) as exc_info:
        get_agent_config("unknown-agent")
    assert exc_info.value.code == "unknown_agent"


def test_get_agent_config_applies_runtime_env_override(tmp_path, monkeypatch) -> None:
    registry_path = tmp_path / "agents.yaml"
    registry_path.write_text(
        """
agents:
  maxima:
    agent_id: maxima
    resource_name: projects/test/locations/us-east1/reasoningEngines/old
    region: us-east1
    streaming_enabled: false
    persistence_enabled: true
    auth_policy: firebase
""",
        encoding="utf-8",
    )

    monkeypatch.setenv("AGENT_REGISTRY_PATH", str(registry_path))
    monkeypatch.setenv(
        "AGENT_MAXIMA_RESOURCE_NAME",
        "projects/test/locations/us-central1/reasoningEngines/new",
    )
    monkeypatch.setenv("AGENT_MAXIMA_REGION", "us-central1")

    agent_config = get_agent_config("maxima")

    assert agent_config.resource_name == (
        "projects/test/locations/us-central1/reasoningEngines/new"
    )
    assert agent_config.region == "us-central1"
