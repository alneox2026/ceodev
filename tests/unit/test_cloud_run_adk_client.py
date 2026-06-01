from __future__ import annotations

import asyncio

import httpx
import pytest

from common.schemas import AgentConfig, ChatRequest
from services.agent_gateway.app.core.errors import ApiError
from services.agent_gateway.app.services.cloud_run_adk_client import CloudRunAdkClient


class _FakeResponse:
    def __init__(
        self,
        *,
        payload: dict | list | None = None,
        text: str = "",
        status_code: int = 200,
        content_type: str = "application/json",
    ) -> None:
        self._payload = payload if payload is not None else {}
        self.text = text
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self.content = text.encode("utf-8") if text else b"{}"

    def json(self):
        if self.text and self.headers.get("content-type") == "application/json":
            raise ValueError("invalid json")
        return self._payload


class _RecordingHttpClient:
    def __init__(self, responses: list[_FakeResponse] | None = None) -> None:
        self.responses = responses or []
        self.post_calls: list[dict[str, object]] = []

    async def post(self, url: str, headers=None, json=None):
        self.post_calls.append({"url": url, "headers": headers, "json": json})
        if not self.responses:
            return _FakeResponse()
        return self.responses.pop(0)

    async def aclose(self) -> None:
        return None


def _agent_config() -> AgentConfig:
    return AgentConfig(
        agent_id="maxima_cloudrun",
        backend="cloud_run_adk",
        base_url="https://maxima-cloudrun-canary.example.run.app",
        app_name="maxima_cloudrun",
        region="us-central1",
        runtime_session_cleanup="none",
    )


async def _fake_authorized_headers(_agent_config) -> dict[str, str]:
    return {"Authorization": "Bearer id-token", "Content-Type": "application/json"}


def test_ensure_session_creates_cloud_run_session() -> None:
    async def _run() -> None:
        http_client = _RecordingHttpClient()
        client = CloudRunAdkClient(http_client=http_client)
        client._authorized_headers = _fake_authorized_headers  # type: ignore[method-assign]

        result = await client.ensure_session(
            agent_config=_agent_config(),
            user_id="user-1",
            request=ChatRequest(message="hello"),
        )

        assert result.thread_id.startswith("thread-")
        assert result.session_id.startswith("session-")
        assert len(http_client.post_calls) == 1
        assert "/apps/maxima_cloudrun/users/user-1/sessions/" in str(
            http_client.post_calls[0]["url"]
        )

    asyncio.run(_run())


def test_chat_buffered_query_posts_run_sse_and_parses_sse_events() -> None:
    async def _run() -> None:
        sse_text = (
            "data: {\"content\":{\"role\":\"model\",\"parts\":[{\"text\":\"hello\"}]}}\n\n"
            "data: {\"content\":{\"role\":\"model\",\"parts\":[{\"text\":\" world\"}]}}\n\n"
        )
        http_client = _RecordingHttpClient(
            responses=[
                _FakeResponse(payload={}),
                _FakeResponse(text=sse_text, content_type="text/event-stream"),
            ]
        )
        client = CloudRunAdkClient(http_client=http_client)
        client._authorized_headers = _fake_authorized_headers  # type: ignore[method-assign]

        response = await client.chat_buffered_query(
            agent_config=_agent_config(),
            user_id="user-1",
            session_id="session-1",
            message="hello",
        )

        assert response.reply_text == "hello world"
        assert len(response.raw_events) == 2
        assert len(http_client.post_calls) == 2
        run_call = http_client.post_calls[1]
        assert str(run_call["url"]).endswith("/run_sse")
        assert run_call["json"] == {
            "app_name": "maxima_cloudrun",
            "user_id": "user-1",
            "session_id": "session-1",
            "new_message": {
                "role": "user",
                "parts": [{"text": "hello"}],
            },
            "streaming": False,
        }

    asyncio.run(_run())


def test_chat_buffered_query_treats_existing_session_as_idempotent() -> None:
    async def _run() -> None:
        sse_text = (
            "data: {\"content\":{\"role\":\"model\",\"parts\":[{\"text\":\"hello\"}]}}\n\n"
        )
        http_client = _RecordingHttpClient(
            responses=[
                _FakeResponse(
                    payload={"detail": "Session already exists: session-1"},
                    status_code=409,
                ),
                _FakeResponse(text=sse_text, content_type="text/event-stream"),
            ]
        )
        client = CloudRunAdkClient(http_client=http_client)
        client._authorized_headers = _fake_authorized_headers  # type: ignore[method-assign]

        response = await client.chat_buffered_query(
            agent_config=_agent_config(),
            user_id="user-1",
            session_id="session-1",
            message="hello",
        )

        assert response.reply_text == "hello"
        assert len(http_client.post_calls) == 2

    asyncio.run(_run())


def test_chat_buffered_query_rejects_empty_model_reply() -> None:
    async def _run() -> None:
        sse_text = (
            "data: {\"author\":\"maxima_cloudrun\",\"content\":{\"role\":\"model\",\"parts\":[]},"
            "\"usage_metadata\":{\"total_token_count\":42}}\n\n"
        )
        http_client = _RecordingHttpClient(
            responses=[
                _FakeResponse(payload={}),
                _FakeResponse(text=sse_text, content_type="text/event-stream"),
            ]
        )
        client = CloudRunAdkClient(http_client=http_client)
        client._authorized_headers = _fake_authorized_headers  # type: ignore[method-assign]

        with pytest.raises(ApiError) as exc_info:
            await client.chat_buffered_query(
                agent_config=_agent_config(),
                user_id="user-1",
                session_id="session-1",
                message="hello",
            )

        assert exc_info.value.status_code == 502
        assert exc_info.value.code == "cloud_run_adk_empty_response"
        assert exc_info.value.details["response_event_count"] == 1
        assert exc_info.value.details["retryable"] is True
        event_summary = exc_info.value.details["event_summaries"][0]
        assert event_summary["author"] == "maxima_cloudrun"
        assert event_summary["content_role"] == "model"
        assert event_summary["content_parts_count"] == 0

    asyncio.run(_run())


def test_chat_buffered_query_maps_cloud_run_error() -> None:
    async def _run() -> None:
        http_client = _RecordingHttpClient(
            responses=[
                _FakeResponse(payload={}),
                _FakeResponse(payload={"detail": "failed"}, status_code=500),
            ]
        )
        client = CloudRunAdkClient(http_client=http_client)
        client._authorized_headers = _fake_authorized_headers  # type: ignore[method-assign]

        with pytest.raises(ApiError) as exc_info:
            await client.chat_buffered_query(
                agent_config=_agent_config(),
                user_id="user-1",
                session_id="session-1",
                message="hello",
            )

        assert exc_info.value.status_code == 502
        assert exc_info.value.code == "cloud_run_adk_error"

    asyncio.run(_run())


def test_chat_buffered_query_redacts_sensitive_error_body_fields() -> None:
    async def _run() -> None:
        http_client = _RecordingHttpClient(
            responses=[
                _FakeResponse(payload={}),
                _FakeResponse(
                    payload={
                        "detail": {
                            "message": "secret user prompt",
                            "text": "secret assistant response",
                            "safe_reason": "upstream failure",
                        }
                    },
                    status_code=500,
                ),
            ]
        )
        client = CloudRunAdkClient(http_client=http_client)
        client._authorized_headers = _fake_authorized_headers  # type: ignore[method-assign]

        with pytest.raises(ApiError) as exc_info:
            await client.chat_buffered_query(
                agent_config=_agent_config(),
                user_id="user-1",
                session_id="session-1",
                message="hello",
            )

        details = exc_info.value.details
        body_excerpt = details["body_excerpt"]
        assert details["operation"] == "run_sse"
        assert details["base_url_host"] == "maxima-cloudrun-canary.example.run.app"
        assert details["retryable"] is True
        assert "upstream failure" in body_excerpt
        assert "secret user prompt" not in body_excerpt
        assert "secret assistant response" not in body_excerpt
        assert "<redacted>" in body_excerpt

    asyncio.run(_run())


def test_chat_buffered_query_maps_read_timeout() -> None:
    class _TimeoutHttpClient:
        async def post(self, url: str, headers=None, json=None):
            request = httpx.Request("POST", url)
            raise httpx.ReadTimeout("read timed out", request=request)

        async def aclose(self) -> None:
            return None

    async def _run() -> None:
        client = CloudRunAdkClient(
            read_timeout_seconds=77,
            http_client=_TimeoutHttpClient(),  # type: ignore[arg-type]
        )
        client._authorized_headers = _fake_authorized_headers  # type: ignore[method-assign]

        with pytest.raises(ApiError) as exc_info:
            await client.chat_buffered_query(
                agent_config=_agent_config(),
                user_id="user-1",
                session_id="session-1",
                message="hello",
            )

        assert exc_info.value.status_code == 504
        assert exc_info.value.code == "cloud_run_adk_read_timeout"
        assert exc_info.value.details["timeout_seconds"] == 77
        assert exc_info.value.details["operation"] == "session_create"
        assert exc_info.value.details["session_id"] == "session-1"

    asyncio.run(_run())
