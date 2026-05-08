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
    log_level: str


@lru_cache(maxsize=1)
def get_settings() -> WorkerSettings:
    return WorkerSettings(
        project_id=os.getenv("GOOGLE_CLOUD_PROJECT", "ceo-dev123").strip() or "ceo-dev123",
        threads_collection=os.getenv("FIRESTORE_THREADS_COLLECTION", "agent_threads").strip() or "agent_threads",
        messages_subcollection=os.getenv("FIRESTORE_MESSAGES_SUBCOLLECTION", "messages").strip() or "messages",
        idempotency_collection=os.getenv("FIRESTORE_IDEMPOTENCY_COLLECTION", "processed_events").strip()
        or "processed_events",
        log_level=os.getenv("WORKER_LOG_LEVEL", "INFO").strip().upper() or "INFO",
    )

