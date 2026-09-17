"""Company operating loop events — durable lineage from goal to memory write.

Loop 23 P0-1: shared contract linking goal → owner agent → run → blocker →
approval → outcome → memory node without a new microservice.

Event lifecycle
---------------
1. ``company.goal.created`` — OKR/goal registered with owner agent.
2. ``company.run.started`` — gated execution run bound to goal + lineage.
3. ``company.approval.pending`` — human gate surfaced (send, CRM, spend, etc.).
4. ``company.outcome.recorded`` — approve / reject / defer / complete recorded.
5. ``company.memory.committed`` — durable Brain write linked to run outcome.

Every event carries ``lineage_id`` so Platform company-loop read model, Brain
goal lineage API, and Lens replay can join on one id.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

CompanyOutcome = Literal[
    "approved",
    "rejected",
    "deferred",
    "completed",
    "failed",
    "cancelled",
]


class CompanyBlockerKind(str, Enum):
    """Why execution is waiting — surfaced on Operator Home blockers pane."""

    APPROVAL = "approval"
    BUDGET = "budget"
    PRODUCT_TRUTH = "product_truth"
    DEPENDENCY = "dependency"
    EXTERNAL = "external"


class CompanyLoopRecord(BaseModel):
    """Durable lineage object persisted across the company operating loop."""

    model_config = ConfigDict(extra="forbid")

    lineage_id: str = Field(min_length=1)
    org_id: str = Field(min_length=1)
    goal_id: Optional[str] = None
    owner_agent: Optional[str] = None
    run_id: Optional[str] = None
    blocker_id: Optional[str] = None
    approval_id: Optional[str] = None
    outcome: Optional[CompanyOutcome] = None
    memory_node_ids: List[str] = Field(default_factory=list)

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str) -> "CompanyLoopRecord":
        return cls.model_validate_json(raw)


class CompanyLoopBasePayload(BaseModel):
    """Fields shared across company-loop event payloads."""

    model_config = ConfigDict(extra="allow")

    lineage_id: str
    org_id: str
    goal_id: Optional[str] = None
    owner_agent: Optional[str] = None
    run_id: Optional[str] = None
    approval_id: Optional[str] = None
    outcome: Optional[CompanyOutcome] = None
    memory_node_ids: List[str] = Field(default_factory=list)


class CompanyGoalCreatedPayload(CompanyLoopBasePayload):
    """Payload for ``company.goal.created``."""

    title: Optional[str] = None
    priority: Optional[str] = None


class CompanyRunStartedPayload(CompanyLoopBasePayload):
    """Payload for ``company.run.started``."""

    surface: Optional[str] = None
    task_summary: Optional[str] = None


class CompanyApprovalPendingPayload(CompanyLoopBasePayload):
    """Payload for ``company.approval.pending``."""

    approval_kind: Optional[str] = None
    blocker_id: Optional[str] = None
    blocker_kind: Optional[CompanyBlockerKind] = None
    impact_preview: Optional[str] = None


class CompanyOutcomeRecordedPayload(CompanyLoopBasePayload):
    """Payload for ``company.outcome.recorded``."""

    recorded_by: Optional[str] = None
    notes: Optional[str] = None


class CompanyMemoryCommittedPayload(CompanyLoopBasePayload):
    """Payload for ``company.memory.committed``."""

    write_id: Optional[str] = None
    lifecycle_stage: Optional[str] = None


COMPANY_LOOP_EVENT_TYPES: frozenset[str] = frozenset({
    "company.goal.created",
    "company.run.started",
    "company.approval.pending",
    "company.outcome.recorded",
    "company.memory.committed",
})


def record_to_goal_created_payload(record: CompanyLoopRecord, **extra: Any) -> Dict[str, Any]:
    """Serialize a CompanyLoopRecord slice for a goal.created event."""
    return CompanyGoalCreatedPayload(
        lineage_id=record.lineage_id,
        org_id=record.org_id,
        goal_id=record.goal_id,
        owner_agent=record.owner_agent,
        **extra,
    ).model_dump()


def validate_company_loop_payload(event_type: str, payload: Dict[str, Any]) -> None:
    """Validate company-loop event payload; raises pydantic.ValidationError on mismatch."""
    if event_type == "company.goal.created":
        CompanyGoalCreatedPayload.model_validate(payload)
    elif event_type == "company.run.started":
        CompanyRunStartedPayload.model_validate(payload)
    elif event_type == "company.approval.pending":
        CompanyApprovalPendingPayload.model_validate(payload)
    elif event_type == "company.outcome.recorded":
        CompanyOutcomeRecordedPayload.model_validate(payload)
    elif event_type == "company.memory.committed":
        CompanyMemoryCommittedPayload.model_validate(payload)
    else:
        raise ValueError(f"unknown company-loop event_type: {event_type}")


def company_loop_record_round_trip(record: CompanyLoopRecord) -> CompanyLoopRecord:
    """JSON round-trip helper for tests and Platform read-model persistence."""
    return CompanyLoopRecord.model_validate(json.loads(record.to_json()))
