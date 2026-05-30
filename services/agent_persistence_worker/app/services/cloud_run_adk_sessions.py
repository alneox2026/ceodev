"""Cloud Run ADK session lifecycle client for the persistence worker."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from urllib.parse import quote

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token

from common.schemas import ThreadDeleteRequestedEvent
from services.agent_persistence_worker.app.core.config import get_settings
from services.agent_persistence_worker.app.core.errors import RetryableWorkerError


class CloudRunAdkSessionNotFoundError(RuntimeError):
    """Signals that a Cloud Run ADK session has already been removed."""


@dataclass
class _TokenCacheEntry:
    audience: str
    token: str
    expires_at_monotonic: float


class CloudRunAdkSessionsClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self._http_client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=timeout_seconds,
                write=timeout_seconds,
                pool=10.0,
            )
        )
        self._token_cache: _TokenCacheEntry | None = None
        self._auth_lock = asyncio.Lock()

    async def close(self) -> None:
        await self._http_client.aclose()

    async def delete_session(self, event: ThreadDeleteRequestedEvent) -> None:
        base_url = (event.agent_base_url or "").rstrip("/")
        app_name = event.agent_app_name or ""
        if not base_url or not app_name:
            raise RetryableWorkerError(
                "Cloud Run ADK delete event is missing base URL or app name."
            )

        path = (
            f"/apps/{quote(app_name, safe='')}"
            f"/users/{quote(event.user_id, safe='')}"
            f"/sessions/{quote(event.session_id, safe='')}"
        )
        headers = await self._authorized_headers(
            audience=event.agent_audience or base_url,
        )
        try:
            response = await self._http_client.delete(
                f"{base_url}{path}",
                headers=headers,
            )
        except httpx.RequestError as exc:
            raise RetryableWorkerError(
                f"Failed to reach Cloud Run ADK for session delete {event.session_id}: {exc}"
            ) from exc

        if response.status_code in {200, 202, 204}:
            return
        if response.status_code == 404:
            raise CloudRunAdkSessionNotFoundError(event.session_id)
        raise RetryableWorkerError(
            "Cloud Run ADK session delete failed with "
            f"{response.status_code}: {response.text}"
        )

    async def _authorized_headers(self, *, audience: str) -> dict[str, str]:
        token = await self._id_token(audience=audience)
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def _id_token(self, *, audience: str) -> str:
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
                raise RetryableWorkerError(
                    "Unable to obtain an identity token for Cloud Run ADK session deletion."
                )
            self._token_cache = _TokenCacheEntry(
                audience=audience,
                token=token,
                expires_at_monotonic=now + 2700,
            )
            return token


_client_singleton: CloudRunAdkSessionsClient | None = None
_client_lock = asyncio.Lock()


async def get_cloud_run_adk_sessions_client() -> CloudRunAdkSessionsClient:
    global _client_singleton
    if _client_singleton is None:
        async with _client_lock:
            if _client_singleton is None:
                settings = get_settings()
                _client_singleton = CloudRunAdkSessionsClient(
                    timeout_seconds=settings.runtime_delete_timeout_seconds,
                )
    return _client_singleton


async def close_cloud_run_adk_sessions_client() -> None:
    global _client_singleton
    if _client_singleton is not None:
        await _client_singleton.close()
        _client_singleton = None
