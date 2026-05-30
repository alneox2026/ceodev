"""Cloud Run-hosted ADK agent client for the gateway."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token

from common.ids import new_session_id, new_thread_id
from common.schemas import AgentConfig, ChatRequest
from services.agent_gateway.app.core.errors import ApiError
from services.agent_gateway.app.services.agent_runtime_client import (
    BufferedAgentResponse,
    SessionResult,
)
from services.agent_gateway.app.services.turn_assembler import TurnAssembler


_client_singleton: "CloudRunAdkClient | None" = None
_client_lock = asyncio.Lock()


@dataclass
class _TokenCacheEntry:
    audience: str
    token: str
    expires_at_monotonic: float


class CloudRunAdkClient:
    def __init__(
        self,
        *,
        connect_timeout_seconds: float = 10.0,
        read_timeout_seconds: float = 60.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.connect_timeout_seconds = connect_timeout_seconds
        self.read_timeout_seconds = read_timeout_seconds
        self._http_client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=connect_timeout_seconds,
                read=read_timeout_seconds,
                write=read_timeout_seconds,
                pool=connect_timeout_seconds,
            )
        )
        self._token_cache: _TokenCacheEntry | None = None
        self._auth_lock = asyncio.Lock()

    async def close(self) -> None:
        await self._http_client.aclose()

    async def ensure_session(
        self,
        *,
        agent_config: AgentConfig,
        user_id: str,
        request: ChatRequest,
    ) -> SessionResult:
        if request.thread_id or request.session_id:
            raise ApiError(
                500,
                "invalid_session_resolution_state",
                "Existing thread sessions must be resolved before reaching Cloud Run ADK.",
            )
        session_id = new_session_id()
        await self._create_or_update_session(
            agent_config=agent_config,
            user_id=user_id,
            session_id=session_id,
        )
        return SessionResult(session_id=session_id, thread_id=new_thread_id())

    async def chat_buffered_query(
        self,
        *,
        agent_config: AgentConfig,
        user_id: str,
        session_id: str,
        message: str,
    ) -> BufferedAgentResponse:
        await self._create_or_update_session(
            agent_config=agent_config,
            user_id=user_id,
            session_id=session_id,
        )
        response_payload = await self._post_run_sse(
            agent_config=agent_config,
            payload={
                "app_name": self._app_name(agent_config),
                "user_id": user_id,
                "session_id": session_id,
                "new_message": {
                    "role": "user",
                    "parts": [{"text": message}],
                },
                "streaming": False,
            },
        )
        raw_events = self._extract_event_payloads(response_payload)
        assembler = TurnAssembler()
        for event in raw_events:
            assembler.add_event(event)
            for fragment in self._extract_text_fragments(event):
                assembler.add_text(fragment)
        return BufferedAgentResponse(
            reply_text=assembler.reply_text(),
            raw_events=raw_events,
        )

    async def _create_or_update_session(
        self,
        *,
        agent_config: AgentConfig,
        user_id: str,
        session_id: str,
    ) -> None:
        await self._post_json(
            agent_config=agent_config,
            path=(
                f"/apps/{quote(self._app_name(agent_config), safe='')}"
                f"/users/{quote(user_id, safe='')}"
                f"/sessions/{quote(session_id, safe='')}"
            ),
            payload={},
            error_code="cloud_run_adk_session_error",
            conflict_ok=True,
        )

    async def _post_run_sse(
        self,
        *,
        agent_config: AgentConfig,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        headers = await self._authorized_headers(agent_config)
        try:
            response = await self._http_client.post(
                f"{self._base_url(agent_config)}/run_sse",
                headers=headers,
                json=payload,
            )
        except httpx.ConnectTimeout as exc:
            raise self._timeout_error("cloud_run_adk_connect_timeout", "connect", exc) from exc
        except httpx.ReadTimeout as exc:
            raise self._timeout_error("cloud_run_adk_read_timeout", "read", exc) from exc
        except httpx.RequestError as exc:
            raise ApiError(
                502,
                "cloud_run_adk_unreachable",
                "The gateway could not reach the Cloud Run ADK agent.",
                {"reason": str(exc)},
            ) from exc

        if response.status_code >= 400:
            raise self._response_error(response, "cloud_run_adk_error")
        return self._decode_run_response(response)

    async def _post_json(
        self,
        *,
        agent_config: AgentConfig,
        path: str,
        payload: dict[str, Any],
        error_code: str,
        conflict_ok: bool = False,
    ) -> dict[str, Any]:
        headers = await self._authorized_headers(agent_config)
        try:
            response = await self._http_client.post(
                f"{self._base_url(agent_config)}{path}",
                headers=headers,
                json=payload,
            )
        except httpx.ConnectTimeout as exc:
            raise self._timeout_error("cloud_run_adk_connect_timeout", "connect", exc) from exc
        except httpx.ReadTimeout as exc:
            raise self._timeout_error("cloud_run_adk_read_timeout", "read", exc) from exc
        except httpx.RequestError as exc:
            raise ApiError(
                502,
                "cloud_run_adk_unreachable",
                "The gateway could not reach the Cloud Run ADK agent.",
                {"reason": str(exc)},
            ) from exc

        if conflict_ok and response.status_code == 409:
            return {}
        if response.status_code >= 400:
            raise self._response_error(response, error_code)
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise ApiError(
                502,
                "invalid_cloud_run_adk_json",
                "Cloud Run ADK returned invalid JSON.",
                {"body": response.text},
            ) from exc

    def _decode_run_response(self, response: httpx.Response) -> dict[str, Any]:
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return {"output": self._parse_sse_text(response.text)}
        try:
            parsed = response.json()
        except ValueError as exc:
            raise ApiError(
                502,
                "invalid_cloud_run_adk_json",
                "Cloud Run ADK returned invalid JSON.",
                {"body": response.text},
            ) from exc
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"output": parsed}
        return {"output": []}

    def _parse_sse_text(self, text: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        data_lines: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                self._append_sse_payload(events, data_lines)
                data_lines = []
                continue
            if line.startswith(":") or line.startswith("event:"):
                continue
            if line.startswith("data:"):
                data_lines.append(line.partition(":")[2].strip())
                continue
            data_lines.append(line)
        self._append_sse_payload(events, data_lines)
        return events

    def _append_sse_payload(
        self,
        events: list[dict[str, Any]],
        data_lines: list[str],
    ) -> None:
        if not data_lines:
            return
        data = "\n".join(data_lines).strip()
        if not data or data == "[DONE]":
            return
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            return
        if isinstance(parsed, dict):
            events.append(parsed)
        elif isinstance(parsed, list):
            events.extend(item for item in parsed if isinstance(item, dict))

    def _extract_event_payloads(self, response_payload: dict[str, Any]) -> list[dict[str, Any]]:
        output = response_payload.get("output", response_payload)
        if isinstance(output, list):
            return [item for item in output if isinstance(item, dict)]
        if isinstance(output, dict):
            events = output.get("events")
            if isinstance(events, list):
                return [item for item in events if isinstance(item, dict)]
            return [output]
        return []

    def _extract_text_fragments(self, event_payload: dict[str, Any]) -> list[str]:
        fragments: list[str] = []

        def collect_parts(container: dict[str, Any] | None) -> None:
            if not isinstance(container, dict):
                return
            parts = container.get("parts")
            if not isinstance(parts, list):
                return
            for part in parts:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    fragments.append(part["text"])

        def walk(value: Any) -> None:
            if isinstance(value, list):
                for item in value:
                    walk(item)
                return
            if not isinstance(value, dict):
                return

            output = value.get("output")
            if isinstance(output, str):
                fragments.append(output)

            if value.get("role") == "model":
                collect_parts(value)

            content = value.get("content")
            if isinstance(content, dict):
                if content.get("role") == "model":
                    collect_parts(content)
                walk(content)

            for nested_key in (
                "result",
                "event",
                "message",
                "response",
                "data",
                "value",
                "payload",
                "output",
            ):
                nested_value = value.get(nested_key)
                if isinstance(nested_value, (dict, list)):
                    walk(nested_value)

        walk(event_payload)
        deduped: list[str] = []
        seen: set[str] = set()
        for fragment in fragments:
            if fragment not in seen:
                seen.add(fragment)
                deduped.append(fragment)
        return deduped

    async def _authorized_headers(self, agent_config: AgentConfig) -> dict[str, str]:
        token = await self._id_token(agent_config)
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def _id_token(self, agent_config: AgentConfig) -> str:
        audience = agent_config.audience or self._base_url(agent_config)
        now = time.monotonic()
        async with self._auth_lock:
            if (
                self._token_cache is not None
                and self._token_cache.audience == audience
                and self._token_cache.expires_at_monotonic > now
            ):
                return self._token_cache.token
            token = await asyncio.to_thread(
                id_token.fetch_id_token,
                GoogleAuthRequest(),
                audience,
            )
            if not token:
                raise ApiError(
                    500,
                    "missing_cloud_run_identity_token",
                    "Unable to obtain an identity token for the Cloud Run ADK agent.",
                )
            self._token_cache = _TokenCacheEntry(
                audience=audience,
                token=token,
                expires_at_monotonic=now + 2700,
            )
            return token

    def _base_url(self, agent_config: AgentConfig) -> str:
        if not agent_config.base_url:
            raise ApiError(
                500,
                "missing_cloud_run_adk_base_url",
                "The Cloud Run ADK agent is missing base_url configuration.",
            )
        return agent_config.base_url.rstrip("/")

    def _app_name(self, agent_config: AgentConfig) -> str:
        if not agent_config.app_name:
            raise ApiError(
                500,
                "missing_cloud_run_adk_app_name",
                "The Cloud Run ADK agent is missing app_name configuration.",
            )
        return agent_config.app_name

    def _timeout_error(
        self,
        code: str,
        timeout_type: str,
        exc: Exception,
    ) -> ApiError:
        timeout_seconds = (
            self.connect_timeout_seconds
            if timeout_type == "connect"
            else self.read_timeout_seconds
        )
        return ApiError(
            504,
            code,
            "The gateway timed out while calling the Cloud Run ADK agent.",
            {
                "reason": str(exc),
                "timeout_seconds": timeout_seconds,
                "timeout_type": timeout_type,
            },
        )

    def _response_error(self, response: httpx.Response, code: str) -> ApiError:
        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text}
        return ApiError(
            502,
            code,
            "Cloud Run ADK returned a non-success response.",
            {"status_code": response.status_code, "body": body},
        )


async def get_cloud_run_adk_client() -> CloudRunAdkClient:
    global _client_singleton
    if _client_singleton is None:
        async with _client_lock:
            if _client_singleton is None:
                from services.agent_gateway.app.core.config import get_settings

                settings = get_settings()
                _client_singleton = CloudRunAdkClient(
                    connect_timeout_seconds=settings.upstream_connect_timeout_seconds,
                    read_timeout_seconds=settings.upstream_read_timeout_seconds,
                )
    return _client_singleton


async def close_cloud_run_adk_client() -> None:
    global _client_singleton
    if _client_singleton is not None:
        await _client_singleton.close()
        _client_singleton = None
