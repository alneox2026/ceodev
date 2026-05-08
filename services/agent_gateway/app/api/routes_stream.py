"""Streaming chat route placeholder for the agent gateway."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from common.schemas import AgentConfig, ChatRequest
from services.agent_gateway.app.core.auth import authenticate_request
from services.agent_gateway.app.core.errors import ApiError
from services.agent_gateway.app.core.logging import log_structured
from services.agent_gateway.app.services.agent_registry import get_agent_config
from services.agent_gateway.app.services.agent_runtime_client import (
    AgentRuntimeClient,
    get_agent_runtime_client,
)
from services.agent_gateway.app.services.pubsub_publisher import get_pubsub_publisher
from services.agent_gateway.app.services.request_context import build_request_context
from services.agent_gateway.app.services.sse_adapter import (
    build_done_event,
    build_error_event,
    build_metadata_event,
    build_token_event,
)
from services.agent_gateway.app.services.turn_event_builder import (
    build_turn_completed_event,
)
from services.agent_gateway.app.services.turn_assembler import TurnAssembler


LOGGER = logging.getLogger(__name__)
router = APIRouter()


@router.post("/v1/agents/{agent_id}/chat/stream")
async def stream_chat(
    request: Request,
    agent_id: str,
    payload: ChatRequest,
) -> StreamingResponse:
    agent_config = get_agent_config(agent_id)
    request_context = build_request_context(
        agent_id=agent_config.agent_id,
        client_turn_id=payload.client_turn_id,
    )
    user_id = await authenticate_request(request)
    runtime_client = await get_agent_runtime_client()
    session_result = await runtime_client.ensure_session(
        agent_config=agent_config,
        user_id=user_id,
        request=payload,
    )
    log_structured(
        LOGGER,
        logging.INFO,
        "gateway_stream_started",
        request_id=request_context.request_id,
        turn_id=request_context.turn_id,
        agent_id=agent_config.agent_id,
        user_id=user_id,
    )

    async def event_stream() -> AsyncIterator[str]:
        assembler = TurnAssembler()
        yield build_metadata_event(
            {
                "ok": True,
                "request_id": request_context.request_id,
                "turn_id": request_context.turn_id,
                "agent_id": agent_config.agent_id,
                "thread_id": session_result.thread_id,
                "session_id": session_result.session_id,
            }
        )
        try:
            async for event in _stream_upstream_events(
                runtime_client=runtime_client,
                agent_config=agent_config,
                user_id=user_id,
                session_id=session_result.session_id,
                message=payload.message,
            ):
                assembler.add_event(event)
                for fragment in runtime_client.extract_text_fragments(event):
                    assembler.add_text(fragment)
                    yield build_token_event(fragment)

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
                    assistant_message=assembler.reply_text(),
                    usage=assembler.usage,
                )
                publish_started_at = datetime.now(timezone.utc)
                publish_result = await publisher.publish_turn_completed(
                    persistence_event
                )
                publish_latency_ms = int(
                    (datetime.now(timezone.utc) - publish_started_at).total_seconds()
                    * 1000
                )
            latency_ms = int(
                (
                    datetime.now(timezone.utc) - request_context.started_at
                ).total_seconds()
                * 1000
            )
            log_structured(
                LOGGER,
                logging.INFO,
                "gateway_stream_completed",
                request_id=request_context.request_id,
                turn_id=request_context.turn_id,
                agent_id=agent_config.agent_id,
                thread_id=session_result.thread_id,
                session_id=session_result.session_id,
                pubsub_message_id=publish_result.message_id if publish_result else None,
                publish_latency_ms=publish_latency_ms,
                latency_ms=latency_ms,
            )
            yield build_done_event(
                {
                    "ok": True,
                    "request_id": request_context.request_id,
                    "turn_id": request_context.turn_id,
                    "agent_id": agent_config.agent_id,
                    "thread_id": session_result.thread_id,
                    "session_id": session_result.session_id,
                    "reply_text": assembler.reply_text(),
                    "usage": assembler.usage,
                    "pubsub_message_id": (
                        publish_result.message_id if publish_result else None
                    ),
                }
            )
        except ApiError as exc:
            log_structured(
                LOGGER,
                logging.WARNING,
                "gateway_stream_failed",
                request_id=request_context.request_id,
                turn_id=request_context.turn_id,
                agent_id=agent_config.agent_id,
                code=exc.code,
                status_code=exc.status_code,
            )
            yield build_error_event(exc.code, exc.message, exc.details)
            yield build_done_event(
                {
                    "ok": False,
                    "request_id": request_context.request_id,
                    "turn_id": request_context.turn_id,
                    "agent_id": agent_config.agent_id,
                    "thread_id": session_result.thread_id,
                    "session_id": session_result.session_id,
                }
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            log_structured(
                LOGGER,
                logging.ERROR,
                "gateway_stream_failed_unexpected",
                request_id=request_context.request_id,
                turn_id=request_context.turn_id,
                agent_id=agent_config.agent_id,
                reason=str(exc),
            )
            yield build_error_event(
                "internal_error",
                "The gateway encountered an unexpected error while streaming.",
                {"reason": str(exc)},
            )
            yield build_done_event(
                {
                    "ok": False,
                    "request_id": request_context.request_id,
                    "turn_id": request_context.turn_id,
                    "agent_id": agent_config.agent_id,
                    "thread_id": session_result.thread_id,
                    "session_id": session_result.session_id,
                }
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_upstream_events(
    *,
    runtime_client: AgentRuntimeClient,
    agent_config: AgentConfig,
    user_id: str,
    session_id: str,
    message: str,
):
    async for event in runtime_client.stream_chat_events(
        agent_config=agent_config,
        user_id=user_id,
        session_id=session_id,
        message=message,
    ):
        yield event
