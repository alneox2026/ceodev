"""Buffered chat route implementation for the agent gateway."""

from __future__ import annotations

from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Request

from common.diagnostics import sanitize_for_diagnostics
from common.schemas import ChatRequest, ChatResponse
from services.agent_gateway.app.core.auth import authenticate_request
from services.agent_gateway.app.core.errors import ApiError
from services.agent_gateway.app.core.logging import log_structured
from services.agent_gateway.app.services.agent_registry import get_agent_config
from services.agent_gateway.app.services.chat_backend_resolver import get_chat_backend_client
from services.agent_gateway.app.services.chat_session_service import get_chat_session_service
from services.agent_gateway.app.services.pubsub_publisher import get_pubsub_publisher
from services.agent_gateway.app.services.request_context import build_request_context
from services.agent_gateway.app.services.turn_event_builder import (
    build_turn_completed_event,
)


LOGGER = logging.getLogger(__name__)
router = APIRouter()


@router.post("/v1/agents/{agent_id}/chat")
async def chat(request: Request, agent_id: str, payload: ChatRequest) -> ChatResponse:
    agent_config = get_agent_config(agent_id)
    request_context = build_request_context(
        agent_id=agent_config.agent_id,
        client_turn_id=payload.client_turn_id,
    )
    user_id = await authenticate_request(request)
    backend_client = await get_chat_backend_client(agent_config)
    session_service = await get_chat_session_service()
    log_structured(
        LOGGER,
        logging.INFO,
        "gateway_chat_started",
        request_id=request_context.request_id,
        turn_id=request_context.turn_id,
        agent_id=agent_config.agent_id,
        user_id=user_id,
    )
    backend_started_at = datetime.now(timezone.utc)
    session_result = await session_service.resolve(
        runtime_client=backend_client,
        agent_config=agent_config,
        user_id=user_id,
        request=payload,
    )
    try:
        agent_response = await backend_client.chat_buffered_query(
            agent_config=agent_config,
            user_id=user_id,
            session_id=session_result.session_id,
            message=payload.message,
        )
    except ApiError as exc:
        backend_latency_ms = int(
            (datetime.now(timezone.utc) - backend_started_at).total_seconds() * 1000
        )
        log_structured(
            LOGGER,
            logging.WARNING,
            "gateway_backend_call_failed",
            request_id=request_context.request_id,
            turn_id=request_context.turn_id,
            agent_id=agent_config.agent_id,
            backend=agent_config.backend,
            thread_id=session_result.thread_id,
            session_id=session_result.session_id,
            session_created=session_result.created_new,
            latency_ms=backend_latency_ms,
            error_code=exc.code,
            error_status_code=exc.status_code,
            error_details=sanitize_for_diagnostics(exc.details),
        )
        raise
    backend_latency_ms = int(
        (datetime.now(timezone.utc) - backend_started_at).total_seconds() * 1000
    )
    log_structured(
        LOGGER,
        logging.INFO,
        "gateway_backend_call_completed",
        request_id=request_context.request_id,
        turn_id=request_context.turn_id,
        agent_id=agent_config.agent_id,
        backend=agent_config.backend,
        thread_id=session_result.thread_id,
        session_id=session_result.session_id,
        session_created=session_result.created_new,
        latency_ms=backend_latency_ms,
        response_event_count=len(agent_response.raw_events),
        reply_text_length=len(agent_response.reply_text),
    )
    usage = {}
    for event in agent_response.raw_events:
        event_usage = event.get("usage_metadata")
        if isinstance(event_usage, dict):
            usage = event_usage
    publish_result = None
    publish_latency_ms = 0
    if agent_config.persistence_enabled:
        publisher = await get_pubsub_publisher()
        persistence_event = build_turn_completed_event(
            request_context=request_context,
            agent_config=agent_config,
            user_id=user_id,
            payload=payload,
            thread_id=session_result.thread_id,
            session_id=session_result.session_id,
            assistant_message=agent_response.reply_text,
            usage=usage,
        )
        publish_started_at = datetime.now(timezone.utc)
        publish_result = await publisher.publish_turn_completed(persistence_event)
        publish_latency_ms = int(
            (datetime.now(timezone.utc) - publish_started_at).total_seconds() * 1000
        )
    latency_ms = int(
        (datetime.now(timezone.utc) - request_context.started_at).total_seconds() * 1000
    )
    log_structured(
        LOGGER,
        logging.INFO,
        "gateway_chat_completed",
        request_id=request_context.request_id,
        turn_id=request_context.turn_id,
        agent_id=agent_config.agent_id,
        thread_id=session_result.thread_id,
        session_id=session_result.session_id,
        session_created=session_result.created_new,
        pubsub_message_id=publish_result.message_id if publish_result else None,
        publish_latency_ms=publish_latency_ms,
        latency_ms=latency_ms,
    )
    return ChatResponse(
        ok=True,
        agent_id=agent_config.agent_id,
        thread_id=session_result.thread_id,
        session_id=session_result.session_id,
        turn_id=request_context.turn_id,
        reply_text=agent_response.reply_text,
    )
