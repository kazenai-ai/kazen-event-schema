"""kazen_event_schema — the canonical KazenEvent shared by the KazenAI SDKs and Agent FinOps.

Usage:
    from kazen_event_schema import KazenEvent, EventType, validate_kazen_event, is_known_event_type

No service-specific imports. Safe to install in any service.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

try:
    from importlib.metadata import PackageNotFoundError, version as _pkg_version

    __version__ = _pkg_version("kazen-event-schema")
except PackageNotFoundError:  # pragma: no cover - source-tree only
    __version__ = "0.6.6"
__all__ = [
    "KazenEvent",
    "EventType",
    "KNOWN_EVENT_TYPES",
    "validate_kazen_event",
    "canonicalize_event_dict",
    "now_ms",
    "new_id",
    "is_known_event_type",
    "normalize_event_type",
    "is_model_call",
    "ValidationError",
    # Typed payload classes
    "ModelCallPayload",
    "ToolCallPayload",
    "ToolRepairPayload",
    "ContextCompactionPayload",
    "GateDecisionPayload",
    "RunLifecyclePayload",
    "FinOpsPayload",
    "FinOpsBudgetPayload",
    "FinOpsBudgetForecastPayload",
    "FinOpsBudgetLevel",
    "validate_payload",
    # Organization spend policy
    "OrgPolicy",
    "PolicyAction",
    "PolicyActionKind",
    "PolicyDecision",
    "PolicyDecisionPayload",
    "FinOpsReserveContext",
    "evaluate_policy",
    "build_policy_decision_event",
    "validate_governance_payload",
    "GOVERNANCE_EVENT_TYPES",
    # Run receipts
    "LensEvalPayload",
    "LensRootCausePayload",
]

from .governance import (  # noqa: E402
    GOVERNANCE_EVENT_TYPES,
    FinOpsReserveContext,
    OrgPolicy,
    PolicyAction,
    PolicyActionKind,
    PolicyDecision,
    PolicyDecisionPayload,
    build_policy_decision_event,
    evaluate_policy,
    validate_governance_payload,
)

from .normalize import is_model_call, normalize_event_type  # noqa: E402

# ---------------------------------------------------------------------------
# Canonical event_type registry (dotted lowercase).
# ---------------------------------------------------------------------------
KNOWN_EVENT_TYPES: frozenset[str] = frozenset({
    "backlog.item_completed",
    "campaign.published",
    "checkpoint.saved",
    "diagnostics.snapshot",
    "event.unknown",
    "drift.detected",
    "finops.budget.denied",
    "finops.budget.reserve",
    "finops.budget.forecast",
    "finops.circuit_breaker.opened",
    "finops.loop.anomaly",
    "finops.stream_cutoff",
    "finops.trajectory",
    "finops.pause",
    "finops.resumed",
    "anomaly.detected",
    "gate.decision",
    # Approvals and memory
    "company.approval.pending",
    "company.memory.committed",
    # Governance / policy plane
    "policy.decision",
    # Evaluation results, joined to run lineage by root_run_id.
    "lens.eval.scored",
    "lens.root_cause.diagnosed",
    "run.task.completed",
    "run.task.started",
    # Runs, context and replay
    "human_gate",
    "brain.retrieve",
    "context.compressed",
    "context.tool_result_compacted",
    "run.evidence_incomplete",
    "run.failed",
    "run.step.checkpointed",
    "llm.call",  # deprecated alias; prefer model.call (normalized at ingest)
    "memory.write",
    "meltdown.onset",
    "model.call",
    "permission_denied",
    "replay.completed",
    "replay.started",
    "routing.model_selected",
    "run.cancelled",
    "run.finished",
    "run.started",
    "sales.opportunity_stage_changed",
    "tool.call",
    "tool.pre_call",
    "tool.repair.applied",
    # Framework lifecycle
    "workflow.start",
    "workflow.end",
    "workflow.step",
    "workflow.suspend",
    "workflow.error",
    "support.case_resolved",
    "user.gate_approved",
    "user.gate_rejected",
    "usage.recorded",
})

# Convenient alias for IDE completions
EventType = str

_EVENT_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")


# ---------------------------------------------------------------------------
# Typed payload classes — one per event_type family.
# extra="allow" so producers can add new fields without breakage; the top-level
# KazenEvent uses extra="forbid" for strict wire compatibility.
# ---------------------------------------------------------------------------

class ModelCallPayload(BaseModel):
    model_config = ConfigDict(extra="allow", protected_namespaces=())
    model: str = ""
    routing_profile: Optional[str] = None
    model_tier: Optional[str] = None
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cache_hit_ratio: Optional[float] = None
    prompt_hash: Optional[str] = None
    response_hash: Optional[str] = None


class ToolRepairPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    scavenged: int = 0
    truncations_fixed: int = 0
    storms_broken: int = 0
    notes_redacted: Optional[str] = None


class ContextCompactionPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    results_shrunk: int = 0
    tokens_saved_est: int = 0
    turn_index: Optional[int] = None
    middle_turns_summarised: Optional[int] = None


class ToolCallPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    tool_name: str = ""
    args_hash: Optional[str] = None
    result_hash: Optional[str] = None


class GateDecisionPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    gate_type: Optional[str] = None           # gate_0 | gate_1 | gate_2
    decision: Optional[str] = None            # approve | deny | escalate
    reason: Optional[str] = None


class RunLifecyclePayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    task_summary: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class FinOpsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    threshold_usd: Optional[float] = None
    current_usd: Optional[float] = None
    reason: Optional[str] = None


FinOpsBudgetLevel = Literal[
    "run",
    "feature",
    "actor",
    "team",
    "workspace",
    "org",
    "business_subject",
    "workflow",
    "business_subject_feature",
]

_FINOPS_BUDGET_LEVELS = frozenset(
    {
        "run",
        "feature",
        "actor",
        "team",
        "workspace",
        "org",
        "business_subject",
        "workflow",
        "business_subject_feature",
    }
)


class FinOpsBudgetPayload(BaseModel):
    """Pre-call FinOps reserve / deny events emitted by kazenai.spine.

    On deny (``finops.budget.denied``), hierarchical budget fields identify which
    envelope tripped: ``level_blocked``, ``dimension``, ``dimension_id``,
    ``window_blocked``, plus ``feature`` and ``actor_id`` for lineage joins.
    All hierarchy fields are optional — legacy events omit them.
    Optional business attribution + decision identity fields.
    """

    model_config = ConfigDict(extra="allow", protected_namespaces=())
    allowed: bool = True
    reason: Optional[str] = None
    reserved_cost_usd: Optional[float] = None
    projected_cost_usd: Optional[float] = None
    actual_cost_usd: Optional[float] = None
    # Optional micros fields; float USD remains for backward compatibility.
    # Canonical meanings live in kazenai-contracts reservation.lifecycle.v1 (do not fork).
    reserved_usd_micros: Optional[int] = None
    projected_usd_micros: Optional[int] = None
    actual_usd_micros: Optional[int] = None
    reservation_id: Optional[str] = None
    call_id: Optional[str] = None
    attempt: Optional[int] = None
    lifecycle_version: Optional[str] = None
    model: str = ""
    feature: str = ""
    actor_id: str = ""
    level_blocked: str = ""
    dimension: str = ""
    dimension_id: str = ""
    window_blocked: str = ""
    # Optional attribution / execution identity (all optional for legacy).
    business_subject_ref: Optional[str] = None
    feature_id: Optional[str] = None
    workflow_id: Optional[str] = None
    operation_id: Optional[str] = None
    attempt_id: Optional[str] = None
    attribution_state: Optional[str] = None
    decision_id: Optional[str] = None

    @field_validator("level_blocked", "dimension", mode="before")
    @classmethod
    def _normalize_hierarchy_level(cls, value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip().lower()
        if not text:
            return ""
        if text not in _FINOPS_BUDGET_LEVELS:
            raise ValueError(
                f"invalid FinOps budget hierarchy level {value!r}; "
                f"expected one of {sorted(_FINOPS_BUDGET_LEVELS)}"
            )
        return text


class FinOpsBudgetForecastPayload(BaseModel):
    """Typed payload for ``finops.budget.forecast``."""

    model_config = ConfigDict(extra="allow")

    budget_usd: float = 0.0
    spent_mtd_usd: float = 0.0
    point_forecast_usd: float = 0.0
    ci_low_usd: float = 0.0
    ci_high_usd: float = 0.0
    confidence: float = 0.9
    forecast_accuracy: float = 0.0
    mean_daily_burn_usd: float = 0.0
    days_remaining: int = 0
    overrun_alert: Optional[Dict[str, Any]] = None


class UsagePayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    module: str
    meter: str
    quantity: int = 1
    cost_cents: int = 0
    source_service: Optional[str] = None


class LensEvalPayload(BaseModel):
    """Typed payload for the canonical `lens.eval.scored` audit event.

    The record run receipts emit when they grade an agent's output. Carries the
    normalized overall score plus the per-metric breakdown, joined to lineage by
    root_run_id.
    """

    model_config = ConfigDict(extra="allow")

    agent: str = ""                 # the agent that was graded
    overall_score: float = 0.0      # normalized 0..1, higher is better
    passed: Optional[bool] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)  # metric -> {score, passed, ...}


class LensRootCausePayload(BaseModel):
    """Typed payload for ``lens.root_cause.diagnosed``.

    Structured root-cause diagnosis for a failed trajectory — primary hypothesis,
  contributing factors, symptoms, and recommended fixes, joined to lineage via
  ``root_run_id``.
    """

    model_config = ConfigDict(extra="allow")

    agent: str = "root_cause"
    failed: bool = False
    primary_cause: Optional[Dict[str, Any]] = None
    contributing_factors: List[Dict[str, Any]] = Field(default_factory=list)
    symptoms: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    causal_chain: List[Dict[str, Any]] = Field(default_factory=list)
    trajectory_score: Optional[float] = None
    trace_digest: str = ""


class FrameworkWorkflowPayload(BaseModel):
    """Typed payload for framework ``workflow.*`` events."""

    model_config = ConfigDict(extra="allow")

    framework: str = ""
    capability: str = "observe"
    operation_id: str = ""
    accounting_owner: str = "sdk"
    wire_version: str = ""
    mode: Optional[str] = None
    phase: Optional[str] = None
    status: Optional[str] = None
    terminal: Optional[str] = None
    error_type: Optional[str] = None
    signal: Optional[str] = None


# Maps event_type → payload validator class.
# Only event types with structured payloads are registered; others are allowed
# to carry arbitrary dicts (no validator registered = no validation performed).
_PAYLOAD_VALIDATORS: Dict[str, type[BaseModel]] = {
    "model.call": ModelCallPayload,
    "llm.call": ModelCallPayload,
    "tool.call": ToolCallPayload,
    "gate.decision": GateDecisionPayload,
    "run.started": RunLifecyclePayload,
    "run.finished": RunLifecyclePayload,
    "run.failed": RunLifecyclePayload,
    "finops.budget.denied": FinOpsBudgetPayload,
    "finops.budget.reserve": FinOpsBudgetPayload,
    "finops.budget.forecast": FinOpsBudgetForecastPayload,
    "finops.circuit_breaker.opened": FinOpsPayload,
    "finops.stream_cutoff": FinOpsPayload,
    "finops.pause": FinOpsPayload,
    "anomaly.detected": FinOpsPayload,
    "finops.trajectory": FinOpsPayload,
    "finops.loop.anomaly": FinOpsPayload,
    "usage.recorded": UsagePayload,
    "tool.repair.applied": ToolRepairPayload,
    "context.tool_result_compacted": ContextCompactionPayload,
    "context.compressed": ContextCompactionPayload,
    "policy.decision": PolicyDecisionPayload,
    "lens.eval.scored": LensEvalPayload,
    "lens.root_cause.diagnosed": LensRootCausePayload,
    "workflow.start": FrameworkWorkflowPayload,
    "workflow.end": FrameworkWorkflowPayload,
    "workflow.step": FrameworkWorkflowPayload,
    "workflow.suspend": FrameworkWorkflowPayload,
    "workflow.error": FrameworkWorkflowPayload,
}


def validate_payload(event_type: str, payload: Dict[str, Any]) -> None:
    """Validate payload contents against the typed spec for this event_type.

    Raises:
        pydantic.ValidationError: if payload fields don't match the typed spec.
        Unknown event types pass through without validation.
    """
    validator_cls = _PAYLOAD_VALIDATORS.get(event_type)
    if validator_cls is not None:
        validator_cls.model_validate(payload)


class KazenEvent(BaseModel):
    """Strict KazenEvent schema v0.3.0 — used across all KazenAI services."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.2"
    ts_ms: int = Field(default_factory=lambda: int(time.time() * 1000))
    timestamp_ms: Optional[int] = None
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), min_length=8)
    org_id: str = "local"
    workspace_id: str = "default"
    project_id: str = "general"
    surface: str = "unspecified"
    client_id: Optional[str] = None  # the client that sent the event, when known
    agent_id: str = "default"
    agent_role: Optional[str] = None
    run_id: Optional[str] = None
    step_id: Optional[str] = None
    parent_step_id: Optional[str] = None
    parent_run_id: Optional[str] = None
    # Lineage. root_run_id is the top of the run tree and links an agent run to
    # its Agent FinOps cost and its run receipt by a single id; trace_id is the
    # OTel-compatible distributed trace id.
    root_run_id: Optional[str] = None
    trace_id: Optional[str] = None
    event_type: str
    tokens: Optional[int] = None
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None
    latency_ms: Optional[int] = None
    gate_decision: Optional[str] = None
    gate_latency_s: Optional[float] = None
    difficulty_score: Optional[float] = None
    artifact_refs: Dict[str, Any] = Field(default_factory=dict)
    stage_budget_usd: Optional[float] = None
    remaining_budget_usd: Optional[float] = None
    projected_total_cost_usd: Optional[float] = None
    avoided_cost_usd: Optional[float] = None
    expected_success_probability: Optional[float] = None
    cost_quality_score: Optional[float] = None
    replay_group_id: Optional[str] = None
    frozen_trace_ref: Optional[str] = None
    drift_baseline_id: Optional[str] = None
    sandbox_backend: Optional[str] = None
    touched_node_ids: list[str] = Field(default_factory=list)
    retrieval_trace_id: Optional[str] = None
    code_graph_snapshot_id: Optional[str] = None
    verification_result: Dict[str, Any] = Field(default_factory=dict)
    payload: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_aliases(cls, data: Any) -> Any:
        """Deterministic alias normalization before defaults apply.

        - ``timestamp_ms`` alone populates ``ts_ms``
        - ``ts_ms`` alone is kept; ``timestamp_ms`` is filled after validate
        - conflicting non-null timestamp aliases are rejected
        - conflicting non-null ``tokens`` / ``tokens_used`` are rejected
        """
        if not isinstance(data, dict):
            return data
        out = dict(data)
        ts = out.get("ts_ms", None)
        ts_alias = out.get("timestamp_ms", None)
        if ts is None and ts_alias is not None:
            out["ts_ms"] = ts_alias
        elif ts is not None and ts_alias is not None:
            try:
                if int(ts) != int(ts_alias):
                    raise ValueError("timestamp_conflict: ts_ms and timestamp_ms disagree")
            except (TypeError, ValueError) as exc:
                if "timestamp_conflict" in str(exc):
                    raise
                raise ValueError("timestamp_conflict: invalid timestamp alias types") from exc

        tokens = out.get("tokens", None)
        tokens_used = out.get("tokens_used", None)
        if tokens is not None and tokens_used is not None:
            try:
                if int(tokens) != int(tokens_used):
                    raise ValueError("tokens_conflict: tokens and tokens_used disagree")
            except (TypeError, ValueError) as exc:
                if "tokens_conflict" in str(exc):
                    raise
                raise ValueError("tokens_conflict: invalid token alias types") from exc
        return out

    @model_validator(mode="after")
    def _sync_compat_fields(self) -> "KazenEvent":
        if self.timestamp_ms is None:
            self.timestamp_ms = self.ts_ms
        if self.tokens_used is None and self.tokens is not None:
            self.tokens_used = self.tokens
        if self.tokens is None and self.tokens_used is not None:
            self.tokens = self.tokens_used
        # Self-rooting: a run with no explicit root is its own root,
        # so every event is always join-able by root_run_id. Child runs must
        # propagate the parent's root_run_id explicitly (a producer concern) — we
        # deliberately do NOT infer it from parent_run_id, which would need a lookup
        # the schema cannot perform. schema_version stays "1.2": these fields are
        # additive + optional, and bumping would break Lens's require_v1 validator
        # (accepts only 1.0/1.1/1.2).
        if self.root_run_id is None and self.run_id is not None:
            self.root_run_id = self.run_id
        return self

    @field_validator("event_type")
    @classmethod
    def _event_type_must_be_dotted_lowercase(cls, v: str) -> str:
        if not _EVENT_TYPE_PATTERN.fullmatch(v):
            raise ValueError(
                f"event_type '{v}' must be dotted lowercase identifiers "
                f"(e.g. 'model.call', 'run.started')"
            )
        return v

    @field_validator("cost_usd", "projected_total_cost_usd", "avoided_cost_usd", mode="after")
    @classmethod
    def _finite_money_fields(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError("invalid_money: cost fields must be finite numbers")
        if v != v or v in (float("inf"), float("-inf")):  # NaN / Inf
            raise ValueError("invalid_money: cost fields must be finite numbers")
        return float(v)

    @field_validator("schema_version")
    @classmethod
    def _supported_schema_version(cls, v: str) -> str:
        if v not in {"1.0", "1.1", "1.2"}:
            raise ValueError("unknown_schema_version: only 1.0, 1.1, or 1.2 is supported")
        return v


def now_ms() -> int:
    return int(time.time() * 1000)


def new_id() -> str:
    return uuid.uuid4().hex


def canonicalize_event_dict(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Validate through the canonical model and return a lossless dump.

    Network ingress callers must still bind authenticated tenant context and
    enforce endpoint-required identity fields; this helper does not authorize.
    """
    return KazenEvent.model_validate(raw).model_dump(mode="python")


def validate_kazen_event(
    rec: Dict[str, Any],
    *,
    strict: bool = False,
    validate_payload_contents: bool = False,
) -> KazenEvent:
    """Parse and validate a dict as a KazenEvent.

    Args:
        rec: Raw dict (e.g. from JSON body).
        strict: If True, also reject unknown event_type values not in KNOWN_EVENT_TYPES.
        validate_payload_contents: If True, also validate the payload dict against the
            typed spec for the event_type (raises ValidationError on mismatch).

    Raises:
        pydantic.ValidationError: if the record is invalid.
    """
    ev = KazenEvent.model_validate(rec)
    if strict and ev.event_type not in KNOWN_EVENT_TYPES:
        raise ValueError(
            f"event_type '{ev.event_type}' is not in the KNOWN_EVENT_TYPES registry. "
            f"Register it or set strict=False to allow unknown types."
        )
    if validate_payload_contents and ev.payload:
        validate_payload(ev.event_type, ev.payload)
    return ev


def is_known_event_type(event_type: str) -> bool:
    """Return True if event_type is in the canonical registry."""
    return event_type in KNOWN_EVENT_TYPES
