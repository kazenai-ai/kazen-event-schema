"""kazen_event_schema — canonical KazenEvent schema shared across all KazenAI services.

Usage:
    from kazen_event_schema import KazenEvent, EventType, validate_kazen_event, is_known_event_type

No orchestrator-specific imports. Safe to install in any service.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

__version__ = "0.6.0"
__all__ = [
    "KazenEvent",
    "EventType",
    "KNOWN_EVENT_TYPES",
    "validate_kazen_event",
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
    "FinOpsOptimizationPayload",
    "FinOpsBudgetPayload",
    "FinOpsBudgetForecastPayload",
    "FinOpsBudgetLevel",
    "validate_payload",
    "MemoryWritePayload",
    "validate_memory_write_payload",
    # Orchestration (Loop 24 — Kazen Route / Conductor-compatible)
    "OrchestrationWorkflow",
    "OrchestrationRole",
    "OrchestrationWorkflowPlannedPayload",
    "OrchestrationStepPayload",
    "OrchestrationWorkflowRevisedPayload",
    "OrchestrationRewardRecordedPayload",
    "ORCHESTRATION_EVENT_TYPES",
    "workflow_to_planned_payload",
    "validate_orchestration_payload",
    "orchestration_workflow_round_trip",
    "TriRole",
    # Company operating loop (Loop 23 P0-1)
    "CompanyLoopRecord",
    "CompanyBlockerKind",
    "CompanyGoalCreatedPayload",
    "CompanyRunStartedPayload",
    "CompanyApprovalPendingPayload",
    "CompanyOutcomeRecordedPayload",
    "CompanyMemoryCommittedPayload",
    "COMPANY_LOOP_EVENT_TYPES",
    "record_to_goal_created_payload",
    "validate_company_loop_payload",
    "company_loop_record_round_trip",
    # Governance / policy plane (Loop 31 P1-2)
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
    # Lens shared eval substrate (Loop 31 P2-1)
    "LensEvalPayload",
    "LensRootCausePayload",
    "GrowthOpsMultichannelPayload",
    "GrowthOpsInboundIntentPayload",
    "GrowthOpsReplyLearnedPayload",
    "MemoryForgottenPayload",
    "MemoryRecallBenchmarkPayload",
    # MCP mesh catalog (Loop 31 P3-1)
    "McpToolSpec",
    "KAZEN_MCP_CATALOG",
    "REQUIRED_CAPABILITIES",
    "catalog_tool_names",
    "required_capabilities_covered",
    "all_required_capabilities_covered",
    "lookup_tool",
    "is_budget_governed",
    "McpMeshSession",
    "InterAgentMesh",
    "BudgetDenied",
    "OrgMismatch",
    "build_mcp_call_event",
    "build_inter_agent_call_event",
]

from .company_loop import (  # noqa: E402
    COMPANY_LOOP_EVENT_TYPES,
    CompanyApprovalPendingPayload,
    CompanyBlockerKind,
    CompanyGoalCreatedPayload,
    CompanyLoopRecord,
    CompanyMemoryCommittedPayload,
    CompanyOutcomeRecordedPayload,
    CompanyRunStartedPayload,
    company_loop_record_round_trip,
    record_to_goal_created_payload,
    validate_company_loop_payload,
)
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
from .memory_write import MemoryWritePayload, validate_memory_write_payload  # noqa: E402
from .mcp_catalog import (  # noqa: E402
    KAZEN_MCP_CATALOG,
    McpToolSpec,
    REQUIRED_CAPABILITIES,
    all_required_capabilities_covered,
    catalog_tool_names,
    is_budget_governed,
    lookup_tool,
    required_capabilities_covered,
)
from .mcp_mesh import (  # noqa: E402
    BudgetDenied,
    InterAgentMesh,
    McpMeshSession,
    OrgMismatch,
    build_inter_agent_call_event,
    build_mcp_call_event,
)
from .orchestration import (  # noqa: E402
    ORCHESTRATION_EVENT_TYPES,
    OrchestrationRole,
    OrchestrationStepPayload,
    OrchestrationWorkflow,
    OrchestrationWorkflowPlannedPayload,
    OrchestrationWorkflowRevisedPayload,
    OrchestrationRewardRecordedPayload,
    TriRole,
    orchestration_workflow_round_trip,
    validate_orchestration_payload,
    workflow_to_planned_payload,
)

from .normalize import is_model_call, normalize_event_type  # noqa: E402

# ---------------------------------------------------------------------------
# Canonical event_type registry (dotted lowercase).
# ---------------------------------------------------------------------------
KNOWN_EVENT_TYPES: frozenset[str] = frozenset({
    "backlog.item_completed",
    "campaign.published",
    "checkpoint.saved",
    "code.approved",
    "context_pack.composed",
    "delivery.pr.created",
    "diagnostics.snapshot",
    "edits.applied",
    "event.unknown",
    "ci.failed",
    "ci.repaired",
    "drift.detected",
    "finops.budget.denied",
    "finops.budget.reserve",
    "finops.budget.forecast",
    "finops.circuit_breaker.opened",
    "finops.stream_cutoff",
    "finops.pause",
    "finops.resumed",
    "finops.optimization.applied",
    "anomaly.detected",
    "fsm.transition",
    "evidence.bundle.written",
    "gate.fast_path_bypass",
    "gate.decision",
    "gate.override.approved",
    "gate.override.requested",
    "finance.review_completed",
    "operating.review_completed",
    "orchestration.step.completed",
    "orchestration.step.started",
    "orchestration.workflow.planned",
    "orchestration.workflow.revised",
    "orchestration.reward.recorded",
    # Company operating loop (Loop 23 P0-1)
    "company.goal.created",
    "company.run.started",
    "company.approval.pending",
    "company.outcome.recorded",
    "company.memory.committed",
    # Governance / policy plane (Loop 31 P1-2)
    "policy.decision",
    # Lens shared eval substrate (Loop 31 P2-1) — one eval score for any agent's
    # output, joined to P1-1 lineage by root_run_id.
    "lens.eval.scored",
    "lens.root_cause.diagnosed",
    "playbook.suggested",
    "playbook.outcome_observed",
    "playbook.version_changed",
    "gatekeeper.complete",
    "gatekeeper.fallback_used",
    "growthops.approval.queued",
    "growthops.multichannel.planned",
    "growthops.inbound.scored",
    "growthops.reply.learned",
    "growthops.critic.verdict",
    "growthops.budget.exceeded",
    "growthops.ingest.completed",
    "growthops.run.completed",
    "growthops.run.failed",
    "growthops.run.started",
    "improvement.eval.baseline",
    "improvement.rollout",
    "run.task.completed",
    "run.task.started",
    # Company goal / OKR events (Month 10 — Self-Directing Intelligence)
    "goals.created",
    "goals.task.dispatched",
    "workforce.task.dispatched",
    "goals.task.completed",
    "goals.task.failed",
    "goals.completed",
    "human_gate",
    "kpi.snapshot",
    "learning.background_review_complete",
    "learning.snapshot",
    "brain.guard",
    "brain.retrieve",
    "context.compressed",
    "context.tool_result_compacted",
    "run.evidence_incomplete",
    "run.failed",
    "run.step.checkpointed",
    "session.indexed",
    "llm.call",  # deprecated alias; prefer model.call (normalized at ingest)
    "mcp.call",
    "memory.write",
    "memory.forgotten",
    "memory.recall_benchmark",
    "meltdown.onset",
    "model.call",
    "permission_denied",
    "patch.applied",
    "plan.written",
    "pr.created",
    "replay.completed",
    "replay.started",
    "router.circuit_breaker_open",
    "routing.model_selected",
    "routing.profile_selected",
    "run.cancelled",
    "run.finished",
    "run.started",
    "sandbox.command",
    "sales.account_researched",
    "sales.approval_granted",
    "sales.approval_rejected",
    "sales.approval_requested",
    "sales.contact_selected",
    "sales.message_drafted",
    "sales.opportunity_stage_changed",
    "sales.opportunity_stalled",
    "sales.outbound_sent",
    "sales.outbound_staged",
    "sales.reply_received",
    "test.completed",
    "test.selected",
    "tool.call",
    "tool.pre_call",
    "tool.repair.applied",
    "support.case_resolved",
    "support.escalated",
    "user.gate_approved",
    "user.gate_rejected",
    "user.hunk_accepted",
    "user.hunk_rejected",
    "user.run_resumed",
    "user.run_started",
    "user.scope_expansion_requested",
    "verify.completed",
    "verification.evidence",
    "usage.recorded",
    "worktree.created",
    "worktree.isolation_unavailable",
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
    brain_trace_node_id: Optional[str] = None


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


class FinOpsOptimizationPayload(BaseModel):
    """Typed payload for ``finops.optimization.applied`` (Loop 31 P4-F1).

    Records measured savings from auto-routing, semantic cache, and prompt
    compression while preserving Lens eval score.
    """

    model_config = ConfigDict(extra="allow")

    agent: str = ""
    baseline_model: str = ""
    selected_model: str = ""
    baseline_cost_usd: float = 0.0
    optimized_cost_usd: float = 0.0
    savings_usd: float = 0.0
    savings_pct: float = 0.0
    baseline_score: float = 0.0
    optimized_score: float = 0.0
    score_preserved: bool = False
    strategies_applied: List[str] = Field(default_factory=list)
    cache_hit: bool = False
    compression_ratio: Optional[float] = None


FinOpsBudgetLevel = Literal["run", "feature", "actor", "team", "workspace", "org"]

_FINOPS_BUDGET_LEVELS = frozenset(
    {"run", "feature", "actor", "team", "workspace", "org"}
)


class FinOpsBudgetPayload(BaseModel):
    """Pre-call FinOps reserve / deny events emitted by kazenai.spine.

    On deny (``finops.budget.denied``), hierarchical budget fields identify which
    envelope tripped: ``level_blocked``, ``dimension``, ``dimension_id``,
    ``window_blocked``, plus ``feature`` and ``actor_id`` for lineage joins.
    All hierarchy fields are optional — legacy events omit them.
    """

    model_config = ConfigDict(extra="allow", protected_namespaces=())
    allowed: bool = True
    reason: Optional[str] = None
    reserved_cost_usd: Optional[float] = None
    projected_cost_usd: Optional[float] = None
    actual_cost_usd: Optional[float] = None
    # FINAL_1 P2-1 — optional micros fields; float USD remains legacy until P2-6 migration.
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
    """Typed payload for ``finops.budget.forecast`` (Loop 31 P4-F2)."""

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
    """Typed payload for the canonical `lens.eval.scored` audit event (Loop 31 P2-1).

    The single record shape Lens emits when it grades ANY agent's output (Brain
    recall, Builder PR, GrowthOps reply, FinOps forecast). Carries the normalized
    overall score plus the per-metric breakdown so "we grade our agents with the
    rigor we grade yours" is one auditable event joined to lineage by root_run_id.
    """

    model_config = ConfigDict(extra="allow")

    agent: str = ""                 # brain | builder | growthops | finops
    overall_score: float = 0.0      # normalized 0..1, higher is better
    passed: Optional[bool] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)  # metric -> {score, passed, ...}


class GrowthOpsMultichannelPayload(BaseModel):
    """Typed payload for ``growthops.multichannel.planned`` (Loop 31 P4-G1).

    Records a governed email + LinkedIn + voice orchestration plan joined to
    call qualification and a shared sequence_id on root_run_id lineage.
    """

    model_config = ConfigDict(extra="allow")

    sequence_id: str = ""
    source_channel: str = ""
    high_intent: bool = False
    channels_planned: List[str] = Field(default_factory=list)
    touch_count: int = 0
    qualification_summary: Dict[str, Any] = Field(default_factory=dict)
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    prospect_email: str = ""
    linkedin_url: str = ""


class GrowthOpsInboundIntentPayload(BaseModel):
    """Typed payload for ``growthops.inbound.scored`` (Loop 31 P4-G2).

    Signal/intent-based inbound scoring — prioritizes warm inbound over cold
    outbound and routes to the right GrowthOps playbook.
    """

    model_config = ConfigDict(extra="allow")

    signal_type: str = ""
    intent_score: float = 0.0
    intent_tier: str = ""  # hot | warm | cold | noise
    recommended_playbook: str = ""
    suppress_cold_outbound: bool = False
    signals_detected: List[str] = Field(default_factory=list)
    reply_classification: str = ""
    prospect_email: str = ""
    source_channel: str = ""


class GrowthOpsReplyLearnedPayload(BaseModel):
    """Typed payload for ``growthops.reply.learned`` (Loop 31 P4-G3).

    Reply-outcome learning that feeds the next sequence touch, with Lens P2-1
    proof of lift over the baseline follow-up.
    """

    model_config = ConfigDict(extra="allow")

    sample_count: int = 0
    conversion_rate: float = 0.0
    winning_themes: List[str] = Field(default_factory=list)
    baseline_lens_score: float = 0.0
    learned_lens_score: float = 0.0
    lift: float = 0.0
    lens_eval_passed: bool = False
    touch_number: int = 0
    sequence_id: str = ""
    eval_kind: str = "reply_outcome_learning"


class MemoryForgottenPayload(BaseModel):
    """Typed payload for ``memory.forgotten`` (Loop 31 P4-B1).

    Machine-unlearning / GDPR erasure — provenance for a deliberately forgotten fact.
    """

    model_config = ConfigDict(extra="allow")

    node_id: str = ""
    content_fingerprint: str = ""
    reason: str = ""
    requested_by: str = ""
    deleted: Dict[str, int] = Field(default_factory=dict)
    found: bool = True


class MemoryRecallBenchmarkPayload(BaseModel):
    """Typed payload for ``memory.recall_benchmark`` (Loop 31 P4-B4).

    Sleep-time consolidation recall lift measurement for the P2-3 drift monitor.
    """

    model_config = ConfigDict(extra="allow")

    recall_before: float = 0.0
    recall_after: float = 0.0
    recall_lift: float = 0.0
    probe_count: int = 0


class LensRootCausePayload(BaseModel):
    """Typed payload for ``lens.root_cause.diagnosed`` (Loop 31 P4-L3).

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


# Maps event_type → payload validator class.
# Only event types with structured payloads are registered; others are allowed
# to carry arbitrary dicts (no validator registered = no validation performed).
_PAYLOAD_VALIDATORS: Dict[str, type[BaseModel]] = {
    "model.call": ModelCallPayload,
    "llm.call": ModelCallPayload,
    "tool.call": ToolCallPayload,
    "mcp.call": ToolCallPayload,
    "gate.decision": GateDecisionPayload,
    "gate.override.requested": GateDecisionPayload,
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
    "finops.optimization.applied": FinOpsOptimizationPayload,
    "usage.recorded": UsagePayload,
    "tool.repair.applied": ToolRepairPayload,
    "context.tool_result_compacted": ContextCompactionPayload,
    "context.compressed": ContextCompactionPayload,
    "orchestration.workflow.planned": OrchestrationWorkflowPlannedPayload,
    "orchestration.step.started": OrchestrationStepPayload,
    "orchestration.step.completed": OrchestrationStepPayload,
    "orchestration.workflow.revised": OrchestrationWorkflowRevisedPayload,
    "orchestration.reward.recorded": OrchestrationRewardRecordedPayload,
    "company.goal.created": CompanyGoalCreatedPayload,
    "company.run.started": CompanyRunStartedPayload,
    "company.approval.pending": CompanyApprovalPendingPayload,
    "company.outcome.recorded": CompanyOutcomeRecordedPayload,
    "company.memory.committed": CompanyMemoryCommittedPayload,
    "policy.decision": PolicyDecisionPayload,
    "lens.eval.scored": LensEvalPayload,
    "lens.root_cause.diagnosed": LensRootCausePayload,
    "growthops.multichannel.planned": GrowthOpsMultichannelPayload,
    "growthops.inbound.scored": GrowthOpsInboundIntentPayload,
    "growthops.reply.learned": GrowthOpsReplyLearnedPayload,
    "memory.forgotten": MemoryForgottenPayload,
    "memory.recall_benchmark": MemoryRecallBenchmarkPayload,
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
    surface: str = "kazenai-agent-builder"
    client_id: Optional[str] = None  # cursor | claude_code | vscode | mcp
    agent_id: str = "devagent"
    agent_role: Optional[str] = None
    run_id: Optional[str] = None
    step_id: Optional[str] = None
    parent_step_id: Optional[str] = None
    parent_run_id: Optional[str] = None
    # Unified cross-product lineage (Loop 31 P0-2). root_run_id is the top of the
    # run tree that links a Builder run + its FinOps cost + Lens trace + Brain
    # writes by a single id; trace_id is the OTel-compatible distributed trace id.
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

    @model_validator(mode="after")
    def _sync_compat_fields(self) -> "KazenEvent":
        if self.timestamp_ms is None:
            self.timestamp_ms = self.ts_ms
        if self.tokens_used is None and self.tokens is not None:
            self.tokens_used = self.tokens
        if self.tokens is None and self.tokens_used is not None:
            self.tokens = self.tokens_used
        # Self-rooting (Loop 31 P0-2): a run with no explicit root is its own root,
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
