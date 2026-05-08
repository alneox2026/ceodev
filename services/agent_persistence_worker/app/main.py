"""FastAPI entrypoint for the persistence worker."""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from services.agent_persistence_worker.app.api.routes_events import router as events_router
from services.agent_persistence_worker.app.core.config import get_settings
from services.agent_persistence_worker.app.core.logging import configure_logging


LOGGER = logging.getLogger(__name__)
SETTINGS = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging(SETTINGS.log_level)
    LOGGER.info(
        "agent_persistence_worker_startup",
        extra={
            "payload": {
                "event": "agent_persistence_worker_startup",
                "project_id": SETTINGS.project_id,
                "threads_collection": SETTINGS.threads_collection,
                "messages_subcollection": SETTINGS.messages_subcollection,
            }
        },
    )
    try:
        yield
    finally:
        LOGGER.info(
            "agent_persistence_worker_shutdown",
            extra={"payload": {"event": "agent_persistence_worker_shutdown"}},
        )


app = FastAPI(
    title="CEOsystem Agent Persistence Worker",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(events_router)
