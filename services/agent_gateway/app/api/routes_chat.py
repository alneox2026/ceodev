"""Buffered chat route implementation for the agent gateway."""

from __future__ import annotations

from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Request

from common.schemas import ChatRequest, ChatResponse
from services.agent_gateway.app.core.auth import authenticate_request
from services.agent_gateway.app.core.logging import log_structured
from services.agent_gateway.app.services.agent_registry import get_agent_config
from services.agent_gateway.app.services.agent_runtime_client import (
    get_agent_runtime_client,
)
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
    runtime_client = await get_agent_runtime_client()
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
    session_result = await session_service.resolve(
        runtime_client=runtime_client,
        agent_config=agent_config,
        user_id=user_id,
        request=payload,
    )
    agent_response = await runtime_client.chat_buffered_query(
        agent_config=agent_config,
        user_id=user_id,
        session_id=session_result.session_id,
        message=payload.message,
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
