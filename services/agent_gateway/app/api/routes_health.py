"""Health and readiness endpoints for the agent gateway."""

from __future__ import annotations

from fastapi import APIRouter


router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, object]:
    return {
        "ok": True,
        "service": "agent-gateway",
        "status": "healthy",
    }


@router.get("/readyz")
async def readyz() -> dict[str, object]:
    return {
        "ok": True,
        "service": "agent-gateway",
        "status": "ready",
    }
