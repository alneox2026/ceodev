"""Pub/Sub event receiver for the persistence worker."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi import HTTPException

from services.agent_persistence_worker.app.core.logging import log_structured
from services.agent_persistence_worker.app.core.errors import RetryableWorkerError
from services.agent_persistence_worker.app.models.events import TurnCompletedEvent
from services.agent_persistence_worker.app.models.pubsub import PubSubPushEnvelope
from services.agent_persistence_worker.app.services.persist_turn import PersistTurnService


LOGGER = logging.getLogger(__name__)
router = APIRouter()
PERSIST_SERVICE = PersistTurnService()


@router.post("/events/pubsub")
async def receive_pubsub_event(envelope: PubSubPushEnvelope) -> dict[str, object]:
    try:
        decoded_payload = envelope.message.decode_json()
        event = TurnCompletedEvent(**decoded_payload)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid Pub/Sub event payload: {exc}",
        ) from exc
    try:
        result = await PERSIST_SERVICE.persist(event)
    except RetryableWorkerError as exc:
        log_structured(
            LOGGER,
            logging.ERROR,
            "worker_event_persist_retryable_failure",
            event_id=event.event_id,
            thread_id=event.thread_id,
            reason=str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Retryable persistence failure: {exc}",
        ) from exc

    log_structured(
        LOGGER,
        logging.INFO,
        "worker_event_persisted",
        event_id=result.event_id,
        thread_id=result.thread_id,
        persisted=result.persisted,
    )
    return {
        "ok": True,
        "event_id": result.event_id,
        "thread_id": result.thread_id,
        "persisted": result.persisted,
    }
