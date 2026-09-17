"""memory.write event payload schema (Month 9)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class MemoryWritePayload(BaseModel):
    schema_id: str = Field(..., description="Governed write schema id, e.g. financial.v1")
    entity_id: str = Field(..., description="Stable entity identifier for the memory node")
    governance_label: str = Field(..., description="Data classification label")
    node_id: str = ""
    source_type: str = ""
    writer_agent: str = ""
    writer_service: str = "brain"
    org_id: str = ""
    workspace_id: str = "default"
    metadata: Dict[str, Any] = Field(default_factory=dict)


def validate_memory_write_payload(data: Dict[str, Any]) -> MemoryWritePayload:
    return MemoryWritePayload.model_validate(data)


def to_kazen_event_fields(payload: MemoryWritePayload) -> Dict[str, Any]:
    return {
        "event_type": "memory.write",
        "payload": payload.model_dump(),
    }
