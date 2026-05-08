"""Helpers to assemble streamed tokens into a final turn result."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TurnAssembler:
    text_fragments: list[str] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    raw_events: list[dict[str, Any]] = field(default_factory=list)

    def add_text(self, value: str) -> None:
        if value:
            self.text_fragments.append(value)

    def add_event(self, event: dict[str, Any]) -> None:
        self.raw_events.append(event)
        usage = event.get("usage_metadata")
        if isinstance(usage, dict):
            self.usage = usage

    def set_usage(self, usage: dict[str, Any]) -> None:
        self.usage = usage

    def reply_text(self) -> str:
        return "".join(self.text_fragments).strip()
