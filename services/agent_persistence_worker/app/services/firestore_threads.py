"""Thread persistence helpers for the worker."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from common.constants import (
    RUNTIME_SESSION_STATUS_DELETE_FAILED,
    RUNTIME_SESSION_STATUS_DELETED,
    STATUS_ACTIVE,
)
from common.schemas import TurnCompletedEvent
from services.agent_persistence_worker.app.core.config import get_settings


class FirestoreThreadsRepository:
    def __init__(self) -> None:
        self._settings = get_settings()

    def document(self, client: Any, thread_id: str):
        return client.collection(self._settings.threads_collection).document(thread_id)

    def load_existing(self, client: Any, thread_id: str) -> dict[str, Any] | None:
        snapshot = self.document(client, thread_id).get()
        if not snapshot.exists:
            return None
        return snapshot.to_dict() or {}

    def add_upsert_to_batch(
        self,
        batch: Any,
        client: Any,
        event: TurnCompletedEvent,
        *,
        existing_thread: dict[str, Any] | None = None,
    ) -> None:
        document = self.document(client, event.thread_id)
        payload: dict[str, Any] = {
            "uid": event.user_id,
            "agent_id": event.agent_id,
            "thread_id": event.thread_id,
            "status": STATUS_ACTIVE,
        }
        if not existing_thread:
            payload["created_at"] = event.created_at
            payload["title"] = event.user_message[:120]

        if self._should_update_summary(existing_thread, event.created_at):
            payload.update(
                {
                    "session_id": event.session_id,
                    "updated_at": event.created_at,
                    "last_message_at": event.created_at,
                    "last_user_message": event.user_message,
                    "last_assistant_message": event.assistant_message,
                }
            )

        batch.set(document, payload, merge=True)

    def _should_update_summary(
        self,
        existing_thread: dict[str, Any] | None,
        event_time: datetime,
    ) -> bool:
        if not existing_thread:
            return True
        existing_time = existing_thread.get("last_message_at")
        if existing_time is None:
            return True
        return event_time >= existing_time

    def add_delete_completed_to_batch(
        self,
        batch: Any,
        client: Any,
        *,
        thread_id: str,
        completed_at: datetime,
        error_code: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "runtime_session_status": RUNTIME_SESSION_STATUS_DELETED,
            "delete_completed_at": completed_at,
            "updated_at": completed_at,
            "last_runtime_error_message": None,
        }
        payload["last_runtime_error_code"] = error_code
        batch.set(self.document(client, thread_id), payload, merge=True)

    def add_delete_failed_to_batch(
        self,
        batch: Any,
        client: Any,
        *,
        thread_id: str,
        failed_at: datetime,
        error_code: str,
        error_message: str,
    ) -> None:
        batch.set(
            self.document(client, thread_id),
            {
                "runtime_session_status": RUNTIME_SESSION_STATUS_DELETE_FAILED,
                "last_runtime_error_code": error_code,
                "last_runtime_error_message": error_message,
                "updated_at": failed_at,
            },
            merge=True,
        )
