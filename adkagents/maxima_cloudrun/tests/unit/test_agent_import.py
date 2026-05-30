"""Smoke tests for the Maxima Cloud Run canary agent."""

from app.agent import MAXIMA_MODEL, root_agent


def test_cloudrun_canary_agent_imports() -> None:
    assert root_agent.name == "maxima_cloudrun"
    assert MAXIMA_MODEL == "gemini-3.5-flash"
