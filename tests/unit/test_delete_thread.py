import asyncio

from common.schemas import ThreadDeleteRequestedEvent
from services.agent_persistence_worker.app.services.delete_thread import DeleteThreadService


class FakeIdempotencyStore:
    def exists(self, client, event_id):
        return True


def _event() -> ThreadDeleteRequestedEvent:
    return ThreadDeleteRequestedEvent(
        event_id="evt-delete",
        agent_id="maxima",
        agent_region="us-central1",
        agent_resource_name="projects/test/locations/us-central1/reasoningEngines/123",
        user_id="user-1",
        thread_id="thread-1",
        session_id="session-1",
    )


def test_duplicate_delete_event_does_not_call_agent_runtime() -> None:
    async def _runtime_client_factory():
        raise AssertionError("runtime delete must not run for duplicate events")

    service = DeleteThreadService(
        idempotency_store=FakeIdempotencyStore(),
        firestore_client_factory=lambda: object(),
        runtime_sessions_client_factory=_runtime_client_factory,
    )

    result = asyncio.run(service.delete_requested(_event()))

    assert result.event_id == "evt-delete"
    assert result.runtime_session_status == "deleted"
