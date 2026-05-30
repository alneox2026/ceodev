"""Backend resolver for gateway chat execution."""

from __future__ import annotations

from typing import Protocol

from common.schemas import AgentConfig, ChatRequest
from services.agent_gateway.app.core.errors import ApiError
from services.agent_gateway.app.services.agent_runtime_client import (
    BufferedAgentResponse,
    SessionResult,
    get_agent_runtime_client,
)
from services.agent_gateway.app.services.cloud_run_adk_client import (
    get_cloud_run_adk_client,
)


class ChatBackendClient(Protocol):
    async def ensure_session(
        self,
        *,
        agent_config: AgentConfig,
        user_id: str,
        request: ChatRequest,
    ) -> SessionResult:
        ...

    async def chat_buffered_query(
        self,
        *,
        agent_config: AgentConfig,
        user_id: str,
        session_id: str,
        message: str,
    ) -> BufferedAgentResponse:
        ...


async def get_chat_backend_client(agent_config: AgentConfig) -> ChatBackendClient:
    if agent_config.backend == "agent_runtime":
        return await get_agent_runtime_client()
    if agent_config.backend == "cloud_run_adk":
        return await get_cloud_run_adk_client()
    raise ApiError(
        500,
        "unsupported_agent_backend",
        "The requested agent backend is not supported by this gateway.",
        {"agent_id": agent_config.agent_id, "backend": agent_config.backend},
    )
