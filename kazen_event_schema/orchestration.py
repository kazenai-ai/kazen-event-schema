"""Orchestration workflow events — Conductor-compatible durable workflow records.

Conductor paper terminology mapping (arXiv 2512.04388 §3.1)
------------------------------------------------------------
KazenAI field          | Conductor term              | Notes
-----------------------|-----------------------------|----------------------------------
``model_id``           | model_id                    | Worker LLM profile per step
``subtasks``           | subtasks                    | NL task description per worker
``access_list``        | access_list                 | Communication topology: indices of
                       |                             | prior steps visible to each worker
``roles``              | (implicit in Trinity)       | thinker | worker | verifier tri-role
``workflow_id``        | workflow instance id        | Durable id for Lens replay
``parent_workflow_id`` | revised workflow parent     | Recursive revision (§3.2)
``lineage_id``         | (KazenAI Loop 23 extension) | Company-loop lineage cross-ref

Event lifecycle
---------------
1. ``orchestration.workflow.planned`` — workflow topology committed before execution.
2. ``orchestration.step.started`` / ``orchestration.step.completed`` — per-step delegation.
3. ``orchestration.workflow.revised`` — verifier-driven topology change (bounded depth).

Every worker delegation MUST emit step events so Lens can replay orchestration (anti-pattern:
Fugu-style black-box routing with no timeline).
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

TriRole = Literal["thinker", "worker", "verifier"]


class OrchestrationRole(str, Enum):
    """Trinity tri-role enum — maps to explore/patch/verify in Kazen Route."""

    THINKER = "thinker"
    WORKER = "worker"
    VERIFIER = "verifier"


class OrchestrationWorkflow(BaseModel):
    """Durable Conductor-compatible workflow record persisted per run."""

    model_config = ConfigDict(extra="forbid")

    workflow_id: str
    model_id: List[str] = Field(default_factory=list)
    subtasks: List[str] = Field(default_factory=list)
    access_list: List[List[int]] = Field(default_factory=list)
    roles: List[TriRole] = Field(default_factory=list)
    parent_workflow_id: Optional[str] = None
    lineage_id: Optional[str] = None
    revision_depth: int = 0

    @field_validator("roles")
    @classmethod
    def _roles_length_matches_model_id(cls, v: List[TriRole], info) -> List[TriRole]:
        model_id = info.data.get("model_id")
        if model_id and v and len(v) != len(model_id):
            raise ValueError(
                f"roles length ({len(v)}) must match model_id length ({len(model_id)})"
            )
        return v

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str) -> "OrchestrationWorkflow":
        return cls.model_validate_json(raw)


class OrchestrationWorkflowPlannedPayload(BaseModel):
    """Payload for ``orchestration.workflow.planned``."""

    model_config = ConfigDict(extra="allow")

    workflow_id: str
    model_id: List[str] = Field(default_factory=list)
    subtasks: List[str] = Field(default_factory=list)
    access_list: List[List[int]] = Field(default_factory=list)
    roles: List[TriRole] = Field(default_factory=list)
    lineage_id: Optional[str] = None


class OrchestrationStepPayload(BaseModel):
    """Shared fields for step started / completed events."""

    model_config = ConfigDict(extra="allow")

    workflow_id: str
    step_index: int = Field(ge=0)
    worker_model: str = ""
    tri_role: TriRole = "worker"
    subtask: str = ""
    cost_usd: Optional[float] = Field(default=None, ge=0)
    lineage_id: Optional[str] = None


class OrchestrationRewardRecordedPayload(BaseModel):
    """Payload for ``orchestration.reward.recorded`` — multi-objective routing reward."""

    model_config = ConfigDict(extra="allow")

    workflow_id: str
    run_id: Optional[str] = None
    scalar: float = Field(ge=0, le=1)
    components: Dict[str, float] = Field(default_factory=dict)
    weights: Dict[str, float] = Field(default_factory=dict)


class OrchestrationWorkflowRevisedPayload(BaseModel):
    """Payload for ``orchestration.workflow.revised`` — recursive topology change."""

    model_config = ConfigDict(extra="allow")

    workflow_id: str
    parent_workflow_id: str
    model_id: List[str] = Field(default_factory=list)
    subtasks: List[str] = Field(default_factory=list)
    access_list: List[List[int]] = Field(default_factory=list)
    roles: List[TriRole] = Field(default_factory=list)
    revision_depth: int = Field(default=1, ge=1)
    lineage_id: Optional[str] = None
    reason: Optional[str] = None


ORCHESTRATION_EVENT_TYPES: frozenset[str] = frozenset({
    "orchestration.workflow.planned",
    "orchestration.step.started",
    "orchestration.step.completed",
    "orchestration.workflow.revised",
    "orchestration.reward.recorded",
})


def workflow_to_planned_payload(workflow: OrchestrationWorkflow) -> Dict[str, Any]:
    """Serialize an OrchestrationWorkflow to a planned-event payload dict."""
    return OrchestrationWorkflowPlannedPayload(
        workflow_id=workflow.workflow_id,
        model_id=list(workflow.model_id),
        subtasks=list(workflow.subtasks),
        access_list=[list(indices) for indices in workflow.access_list],
        roles=list(workflow.roles),
        lineage_id=workflow.lineage_id,
    ).model_dump()


def validate_orchestration_payload(event_type: str, payload: Dict[str, Any]) -> None:
    """Validate orchestration event payload; raises pydantic.ValidationError on mismatch."""
    if event_type == "orchestration.workflow.planned":
        OrchestrationWorkflowPlannedPayload.model_validate(payload)
    elif event_type in ("orchestration.step.started", "orchestration.step.completed"):
        OrchestrationStepPayload.model_validate(payload)
    elif event_type == "orchestration.workflow.revised":
        OrchestrationWorkflowRevisedPayload.model_validate(payload)
    elif event_type == "orchestration.reward.recorded":
        OrchestrationRewardRecordedPayload.model_validate(payload)
    else:
        raise ValueError(f"unknown orchestration event_type: {event_type}")


def orchestration_workflow_round_trip(workflow: OrchestrationWorkflow) -> OrchestrationWorkflow:
    """JSON round-trip helper for tests and Lens persistence."""
    return OrchestrationWorkflow.model_validate(json.loads(workflow.to_json()))
