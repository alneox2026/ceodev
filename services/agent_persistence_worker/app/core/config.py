"""Typed configuration for the persistence worker."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class WorkerSettings:
    project_id: str
    threads_collection: str
    messages_subcollection: str
    idempotency_collection: str
    runtime_delete_timeout_seconds: float
    log_level: str
    eventarc_auth_required: bool
    eventarc_allowed_service_account: str
    eventarc_audience: str


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def get_settings() -> WorkerSettings:
    return WorkerSettings(
        project_id=os.getenv("GOOGLE_CLOUD_PROJECT", "ceo-dev123").strip() or "ceo-dev123",
        threads_collection=os.getenv("FIRESTORE_THREADS_COLLECTION", "agent_threads").strip() or "agent_threads",
        messages_subcollection=os.getenv("FIRESTORE_MESSAGES_SUBCOLLECTION", "messages").strip() or "messages",
        idempotency_collection=os.getenv("FIRESTORE_IDEMPOTENCY_COLLECTION", "processed_events").strip()
        or "processed_events",
        runtime_delete_timeout_seconds=float(os.getenv("RUNTIME_DELETE_TIMEOUT_SECONDS", "30")),
        log_level=os.getenv("WORKER_LOG_LEVEL", "INFO").strip().upper() or "INFO",
        eventarc_auth_required=_parse_bool(
            os.getenv("WORKER_REQUIRE_EVENTARC_AUTH"),
            default=False,
        ),
        eventarc_allowed_service_account=os.getenv(
            "WORKER_EVENTARC_ALLOWED_SERVICE_ACCOUNT",
            "",
        ).strip(),
        eventarc_audience=os.getenv("WORKER_EVENTARC_AUDIENCE", "").strip(),
    )
