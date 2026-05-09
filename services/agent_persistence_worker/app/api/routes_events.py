"""Pub/Sub event receiver for the persistence worker."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi import HTTPException

from common.constants import EVENT_TYPE_THREAD_DELETE_REQUESTED, EVENT_TYPE_TURN_COMPLETED
from services.agent_persistence_worker.app.core.logging import log_structured
from services.agent_persistence_worker.app.core.errors import RetryableWorkerError
from services.agent_persistence_worker.app.models.events import (
    ThreadDeleteRequestedEvent,
    TurnCompletedEvent,
)
from services.agent_persistence_worker.app.models.pubsub import PubSubPushEnvelope
from services.agent_persistence_worker.app.services.delete_thread import DeleteThreadService
from services.agent_persistence_worker.app.services.persist_turn import PersistTurnService


LOGGER = logging.getLogger(__name__)
router = APIRouter()
PERSIST_SERVICE = PersistTurnService()
DELETE_THREAD_SERVICE = DeleteThreadService()


@router.post("/events/pubsub")
async def receive_pubsub_event(envelope: PubSubPushEnvelope) -> dict[str, object]:
    try:
        decoded_payload = envelope.message.decode_json()
        event_type = str(decoded_payload.get("event_type", "")).strip()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid Pub/Sub event payload: {exc}",
        ) from exc

    if event_type == EVENT_TYPE_TURN_COMPLETED:
        return await _handle_turn_completed(decoded_payload)
    if event_type == EVENT_TYPE_THREAD_DELETE_REQUESTED:
        return await _handle_thread_delete_requested(decoded_payload)
    raise HTTPException(
        status_code=400,
        detail=f"Unsupported event type: {event_type or 'missing'}",
    )


async def _handle_turn_completed(decoded_payload: dict[str, object]) -> dict[str, object]:
    try:
        event = TurnCompletedEvent(**decoded_payload)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid turn-completed payload: {exc}",
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


async def _handle_thread_delete_requested(
    decoded_payload: dict[str, object],
) -> dict[str, object]:
    try:
        event = ThreadDeleteRequestedEvent(**decoded_payload)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid thread-delete payload: {exc}",
        ) from exc
    try:
        result = await DELETE_THREAD_SERVICE.delete_requested(event)
    except RetryableWorkerError as exc:
        log_structured(
            LOGGER,
            logging.ERROR,
            "worker_thread_delete_retryable_failure",
            event_id=event.event_id,
            thread_id=event.thread_id,
            reason=str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Retryable delete failure: {exc}",
        ) from exc

    log_structured(
        LOGGER,
        logging.INFO,
        "worker_thread_delete_processed",
        event_id=result.event_id,
        thread_id=result.thread_id,
        runtime_session_status=result.runtime_session_status,
    )
    return {
        "ok": True,
        "event_id": result.event_id,
        "thread_id": result.thread_id,
        "runtime_session_status": result.runtime_session_status,
    }
