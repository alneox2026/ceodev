from types import SimpleNamespace

from fastapi.testclient import TestClient

from services.agent_gateway.app.main import app
from services.agent_gateway.app.api import routes_chat
from services.agent_gateway.app.api import routes_stream


client = TestClient(app)


class FakeAgentRuntimeClient:
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
        yield {
            "content": {
                "role": "model",
                "parts": [{"text": f"echo:{message}"}],
            },
            "usage_metadata": {"total_token_count": 12},
        }

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
