from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from common.schemas import AgentConfig
from services.agent_gateway.app.services.agent_runtime_client import (
    AgentRuntimeClient,
    STREAM_RUN_CONFIG,
)


class _FakeStreamResponse:
    status_code = 200

    async def __aenter__(self) -> "_FakeStreamResponse":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def aiter_lines(self) -> AsyncIterator[str]:
        yield "event: message"
        yield 'data: {"content":{"role":"model","parts":[{"text":"hello"}]}}'
        yield ""

    async def aread(self) -> bytes:
        return b""


class _RecordingAsyncClient:
    def __init__(self) -> None:
        self.stream_calls: list[dict[str, object]] = []

    def stream(self, method: str, url: str, headers=None, json=None):
        self.stream_calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "json": json,
            }
        )
        return _FakeStreamResponse()

    async def aclose(self) -> None:
        return None


def test_stream_chat_events_requests_sse_run_config() -> None:
    async def _run() -> None:
        http_client = _RecordingAsyncClient()
        runtime_client = AgentRuntimeClient(http_client=http_client)

        async def _fake_authorized_headers() -> dict[str, str]:
            return {
                "Authorization": "Bearer test-token",
                "Content-Type": "application/json",
            }

        runtime_client._authorized_headers = _fake_authorized_headers  # type: ignore[method-assign]

        agent_config = AgentConfig(
            agent_id="maxima",
            resource_name="projects/test/locations/us-central1/reasoningEngines/123",
            region="us-central1",
        )

        events = [
            event
            async for event in runtime_client.stream_chat_events(
                agent_config=agent_config,
                user_id="user-1",
                session_id="session-1",
                message="hello",
            )
        ]

        assert len(events) == 1
        assert len(http_client.stream_calls) == 1

        stream_call = http_client.stream_calls[0]
        assert stream_call["method"] == "POST"
        assert stream_call["json"] == {
            "class_method": "async_stream_query",
            "input": {
                "user_id": "user-1",
                "session_id": "session-1",
                "message": "hello",
            },
            "run_config": STREAM_RUN_CONFIG,
        }

    asyncio.run(_run())
