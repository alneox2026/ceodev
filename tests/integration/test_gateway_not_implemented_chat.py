from types import SimpleNamespace

from fastapi.testclient import TestClient

from services.agent_gateway.app.main import app
from services.agent_gateway.app.api import routes_chat
from services.agent_gateway.app.api import routes_stream
from services.agent_gateway.app.services.agent_runtime_client import UpstreamStreamEvent


client = TestClient(app)


class FakeAgentRuntimeClient:
    def __init__(self, upstream_events=None):
        self._upstream_events = upstream_events or [
            UpstreamStreamEvent(
                event_name="message",
                payload={
                    "content": {
                        "role": "model",
                        "parts": [{"text": "echo:hello"}],
                    },
                    "usage_metadata": {"total_token_count": 12},
                },
            )
        ]

    async def ensure_session(self, *, agent_config, user_id, request):
        return SimpleNamespace(
            session_id=request.session_id or "session-fake",
            thread_id=request.thread_id or "thread-fake",
        )

    async def chat(self, *, agent_config, user_id, session_id, message):
        return SimpleNamespace(
            reply_text=f"echo:{message}",
            raw_events=[],
        )

    async def stream_chat_events(self, *, agent_config, user_id, session_id, message):
        for upstream_event in self._upstream_events:
            yield upstream_event

    def extract_text_fragments(self, event):
        parts = event.get("content", {}).get("parts", [])
        return [part["text"] for part in parts if isinstance(part.get("text"), str)]


class FakePublisher:
    async def publish_turn_completed(self, event):
        return SimpleNamespace(message_id="msg-fake")


async def _fake_authenticate_request(request) -> str:
    return "user-test"


async def _fake_get_agent_runtime_client() -> FakeAgentRuntimeClient:
    return FakeAgentRuntimeClient()


async def _fake_get_pubsub_publisher() -> FakePublisher:
    return FakePublisher()


def _make_runtime_client(upstream_events=None):
    async def _fake_runtime_client():
        return FakeAgentRuntimeClient(upstream_events=upstream_events)

    return _fake_runtime_client


def test_buffered_chat_returns_structured_success(monkeypatch) -> None:
    monkeypatch.setattr(routes_chat, "authenticate_request", _fake_authenticate_request)
    monkeypatch.setattr(routes_chat, "get_agent_runtime_client", _fake_get_agent_runtime_client)
    monkeypatch.setattr(routes_chat, "get_pubsub_publisher", _fake_get_pubsub_publisher)

    response = client.post("/v1/agents/maxima/chat", json={"message": "hello"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["agent_id"] == "maxima"
    assert payload["thread_id"] == "thread-fake"
    assert payload["session_id"] == "session-fake"
    assert payload["reply_text"] == "echo:hello"


def test_buffered_chat_rejects_unknown_agent(monkeypatch) -> None:
    monkeypatch.setattr(routes_chat, "authenticate_request", _fake_authenticate_request)
    monkeypatch.setattr(routes_chat, "get_agent_runtime_client", _fake_get_agent_runtime_client)
    monkeypatch.setattr(routes_chat, "get_pubsub_publisher", _fake_get_pubsub_publisher)

    response = client.post("/v1/agents/unknown/chat", json={"message": "hello"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "unknown_agent"


def test_stream_chat_returns_normalized_sse_contract(monkeypatch) -> None:
    monkeypatch.setattr(routes_stream, "authenticate_request", _fake_authenticate_request)
    monkeypatch.setattr(routes_stream, "get_agent_runtime_client", _fake_get_agent_runtime_client)
    monkeypatch.setattr(routes_stream, "get_pubsub_publisher", _fake_get_pubsub_publisher)
    response = client.post("/v1/agents/maxima/chat/stream", json={"message": "hello"})
    assert response.status_code == 200
    assert "event: metadata" in response.text
    assert 'data: {"text": "echo:hello"}' in response.text
    assert "event: done" in response.text
    assert '"reply_text": "echo:hello"' in response.text
    assert '"pubsub_message_id": "msg-fake"' in response.text


def test_stream_chat_logs_fragment_counters_for_multiple_text_events(monkeypatch) -> None:
    log_calls: list[dict[str, object]] = []
    upstream_events = [
        UpstreamStreamEvent(
            event_name="message_start",
            payload={
                "content": {
                    "role": "model",
                    "parts": [{"text": "echo:"}],
                }
            },
        ),
        UpstreamStreamEvent(
            event_name="message_delta",
            payload={
                "content": {
                    "role": "model",
                    "parts": [{"text": "hello"}],
                },
                "usage_metadata": {"total_token_count": 12},
            },
        ),
    ]

    def _capture_log(_logger, _level, event, **fields):
        log_calls.append({"event": event, **fields})

    monkeypatch.setattr(routes_stream, "authenticate_request", _fake_authenticate_request)
    monkeypatch.setattr(
        routes_stream,
        "get_agent_runtime_client",
        _make_runtime_client(upstream_events=upstream_events),
    )
    monkeypatch.setattr(routes_stream, "get_pubsub_publisher", _fake_get_pubsub_publisher)
    monkeypatch.setattr(routes_stream, "log_structured", _capture_log)

    response = client.post("/v1/agents/maxima/chat/stream", json={"message": "hello"})

    assert response.status_code == 200
    assert response.text.count("event: token") == 2
    assert '"reply_text": "echo:hello"' in response.text

    completion_log = next(
        call for call in log_calls if call["event"] == "gateway_stream_completed"
    )
    assert completion_log["upstream_sse_message_count"] == 2
    assert completion_log["upstream_text_event_count"] == 2
    assert completion_log["upstream_text_fragment_count"] == 2
    assert completion_log["normalized_token_event_count"] == 2
    assert completion_log["reply_text_char_count"] == len("echo:hello")
    assert completion_log["first_token_latency_ms"] is not None


def test_stream_chat_emits_only_new_suffix_for_cumulative_partials(monkeypatch) -> None:
    upstream_events = [
        UpstreamStreamEvent(
            event_name="message_start",
            payload={
                "content": {
                    "role": "model",
                    "parts": [{"text": "echo:"}],
                }
            },
        ),
        UpstreamStreamEvent(
            event_name="message_delta",
            payload={
                "content": {
                    "role": "model",
                    "parts": [{"text": "echo:hello"}],
                },
                "usage_metadata": {"total_token_count": 12},
            },
        ),
    ]

    monkeypatch.setattr(routes_stream, "authenticate_request", _fake_authenticate_request)
    monkeypatch.setattr(
        routes_stream,
        "get_agent_runtime_client",
        _make_runtime_client(upstream_events=upstream_events),
    )
    monkeypatch.setattr(routes_stream, "get_pubsub_publisher", _fake_get_pubsub_publisher)

    response = client.post("/v1/agents/maxima/chat/stream", json={"message": "hello"})

    assert response.status_code == 200
    assert response.text.count("event: token") == 2
    assert 'data: {"text": "echo:"}' in response.text
    assert 'data: {"text": "hello"}' in response.text
    assert '"reply_text": "echo:hello"' in response.text


def test_stream_chat_debug_log_captures_upstream_shape_without_text(monkeypatch) -> None:
    log_calls: list[dict[str, object]] = []
    upstream_events = [
        UpstreamStreamEvent(
            event_name="metadata",
            payload={"type": "metadata", "sequence": 1},
        ),
        UpstreamStreamEvent(
            event_name="message",
            payload={
                "content": {
                    "role": "model",
                    "parts": [{"text": "echo:hello"}],
                },
                "usage_metadata": {"total_token_count": 12},
            },
        ),
    ]

    def _capture_log(_logger, _level, event, **fields):
        log_calls.append({"event": event, **fields})

    monkeypatch.setattr(routes_stream, "authenticate_request", _fake_authenticate_request)
    monkeypatch.setattr(
        routes_stream,
        "get_agent_runtime_client",
        _make_runtime_client(upstream_events=upstream_events),
    )
    monkeypatch.setattr(routes_stream, "get_pubsub_publisher", _fake_get_pubsub_publisher)
    monkeypatch.setattr(routes_stream, "log_structured", _capture_log)
    monkeypatch.setattr(
        routes_stream,
        "get_settings",
        lambda: SimpleNamespace(stream_debug=True),
    )

    response = client.post("/v1/agents/maxima/chat/stream", json={"message": "hello"})

    assert response.status_code == 200
    assert response.text.count("event: token") == 1

    debug_log = next(
        call for call in log_calls
        if call["event"] == "gateway_stream_upstream_diagnostics"
    )
    assert debug_log["outcome"] == "completed"
    assert debug_log["upstream_sse_message_count"] == 2
    assert debug_log["upstream_text_event_count"] == 1
    assert debug_log["upstream_text_fragment_count"] == 1
    assert debug_log["normalized_token_event_count"] == 1
    assert debug_log["upstream_event_names"] == ["metadata", "message"]
    assert debug_log["upstream_fragment_counts"] == [0, 1]
    assert debug_log["upstream_payload_keys"] == [
        ["sequence", "type"],
        ["content", "usage_metadata"],
    ]
    assert debug_log["upstream_fragment_lengths"] == [[], [len("echo:hello")]]
    assert "echo:hello" not in str(debug_log)
