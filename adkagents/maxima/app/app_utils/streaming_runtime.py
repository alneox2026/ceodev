from __future__ import annotations

from collections.abc import AsyncIterable, Mapping
from typing import Any

from vertexai.agent_engines.templates.adk import AdkApp


DEFAULT_STREAMING_MODE = "none"


def merge_stream_run_config(
    run_config: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged_run_config = dict(run_config or {})
    merged_run_config.setdefault("streaming_mode", DEFAULT_STREAMING_MODE)
    return merged_run_config


class StreamingDefaultAdkApp(AdkApp):
    async def async_stream_query(
        self,
        *,
        message: str | dict[str, Any],
        user_id: str,
        session_id: str | None = None,
        session_events: list[dict[str, Any]] | None = None,
        run_config: dict[str, Any] | None = None,
        **kwargs,
    ) -> AsyncIterable[dict[str, Any]]:
        effective_run_config = merge_stream_run_config(run_config)
        async for event in super().async_stream_query(
            message=message,
            user_id=user_id,
            session_id=session_id,
            session_events=session_events,
            run_config=effective_run_config,
            **kwargs,
        ):
            yield event
