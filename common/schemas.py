"""Shared Pydantic schemas for the gateway and persistence worker."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from common.constants import EVENT_TYPE_TURN_COMPLETED, STATUS_COMPLETED
from common.ids import validate_agent_id, validate_session_id, validate_thread_id


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    resource_name: str
    region: str
    streaming_enabled: bool = True
    persistence_enabled: bool = True
    auth_policy: str = "firebase"

    @field_validator("agent_id")
    @classmethod
    def validate_agent(cls, value: str) -> str:
        return validate_agent_id(value)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=20000)
    thread_id: str | None = None
    session_id: str | None = None
    client_turn_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message must not be empty.")
        return cleaned

    @field_validator("thread_id")
    @classmethod
    def validate_thread(cls, value: str | None) -> str | None:
        return validate_thread_id(value)

    @field_validator("session_id")
    @classmethod
    def validate_session(cls, value: str | None) -> str | None:
        return validate_session_id(value)


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = True
    agent_id: str
    thread_id: str
    session_id: str
    turn_id: str
    reply_text: str


class TurnCompletedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str = EVENT_TYPE_TURN_COMPLETED
    event_id: str
    turn_id: str
    agent_id: str
    user_id: str
    thread_id: str
    session_id: str
    user_message: str
    assistant_message: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = STATUS_COMPLETED
    usage: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("agent_id")
    @classmethod
    def validate_agent(cls, value: str) -> str:
        return validate_agent_id(value)

