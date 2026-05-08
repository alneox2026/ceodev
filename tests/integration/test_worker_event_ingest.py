import base64
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from services.agent_persistence_worker.app.main import app
from services.agent_persistence_worker.app.api import routes_events


client = TestClient(app)


async def _fake_persist(event):
    return SimpleNamespace(
        event_id=event.event_id,
        thread_id=event.thread_id,
        persisted=True,
    )


def test_worker_accepts_valid_pubsub_event(monkeypatch) -> None:
    monkeypatch.setattr(routes_events.PERSIST_SERVICE, "persist", _fake_persist)
    payload = {
        "event_type": "agent.turn.completed",
        "event_id": "evt-test",
        "turn_id": "turn-test",
        "agent_id": "maxima",
        "user_id": "user-123",
        "thread_id": "thread-test",
        "session_id": "session-test",
        "user_message": "hello",
        "assistant_message": "hi there",
    }
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    envelope = {
        "message": {
            "data": encoded,
            "messageId": "msg-1",
        },
        "subscription": "projects/ceo-dev123/subscriptions/test-sub",
    }

    response = client.post("/events/pubsub", json=envelope)
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_worker_rejects_invalid_pubsub_event() -> None:
    response = client.post("/events/pubsub", json={"message": {"data": "", "messageId": "x"}, "subscription": "sub"})
    assert response.status_code >= 400
