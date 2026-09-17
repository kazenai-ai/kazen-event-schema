"""Loop 31 P1-2 — the unified org governance/policy plane (single source of truth).

One `OrgPolicy` object expresses the clauses a CISO/CFO cares about:

  * no agent spends more than $X                 -> max_spend_usd
  * no email/PR/external-send without approval   -> require_approval_for_external_send
  * no code merged without security review        -> require_security_review_for_merge
  * no memory write without a citation            -> require_citation_for_memory_write

Every service imports the SAME `evaluate_policy()` and emits the SAME canonical
`policy.decision` KazenEvent, so "flipping one org policy changes behaviour in all
five agents" and one audit log captures every decision — something no point-tool
stack can offer. No parallel policy/audit model lives in any service; this is it.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# The four governed action classes, one per enforcement surface family.
PolicyActionKind = Literal["spend", "external_send", "code_merge", "memory_write"]

GOVERNANCE_EVENT_TYPES = frozenset({"policy.decision"})


class OrgPolicy(BaseModel):
    """A single org-scoped policy enforced identically across all five agents."""

    model_config = ConfigDict(extra="allow")

    org_id: str = "local"
    policy_version: int = 1
    # None means "no cap"; a number caps per-action spend in USD.
    max_spend_usd: Optional[float] = None
    require_approval_for_external_send: bool = False
    require_security_review_for_merge: bool = False
    require_citation_for_memory_write: bool = False
    updated_at_ms: int = Field(default_factory=lambda: int(time.time() * 1000))


class PolicyAction(BaseModel):
    """A normalised action a service wants to take, checked against OrgPolicy."""

    model_config = ConfigDict(extra="allow")

    kind: PolicyActionKind
    org_id: str = "local"
    surface: Optional[str] = None  # emitting agent, e.g. kazenai-agent-brain
    run_id: Optional[str] = None
    root_run_id: Optional[str] = None
    # Per-kind context (only the field relevant to `kind` is consulted):
    cost_usd: Optional[float] = None      # spend
    workspace_id: Optional[str] = None    # spend → FinOps workspace scope
    feature: Optional[str] = None         # spend → FinOps feature slug
    actor_id: Optional[str] = None        # spend → FinOps actor (from Principal)
    finops: Optional["FinOpsReserveContext"] = None  # spend → hierarchical budget outcome
    approved: bool = False                 # external_send
    security_reviewed: bool = False        # code_merge
    has_citation: bool = False             # memory_write


class FinOpsReserveContext(BaseModel):
    """Outcome of a FinOps `/v1/budget/check` — hierarchical budgets defer here, not OrgPolicy."""

    model_config = ConfigDict(extra="allow")

    allowed: bool = True
    reason: Optional[str] = None
    level_blocked: Optional[str] = None   # run | feature | actor | team | workspace | org
    dimension_id: Optional[str] = None
    window_blocked: Optional[str] = None  # daily | monthly | run


class PolicyDecision(BaseModel):
    model_config = ConfigDict(extra="allow")

    allowed: bool
    decision: Literal["allow", "deny"]
    action_kind: PolicyActionKind
    clause: Optional[str] = None  # the OrgPolicy field that drove a deny
    reason: Optional[str] = None
    policy_version: int = 1


class PolicyDecisionPayload(BaseModel):
    """Typed payload for the canonical `policy.decision` audit event."""

    model_config = ConfigDict(extra="allow")

    action_kind: str = ""
    decision: str = ""           # allow | deny
    clause: Optional[str] = None
    reason: Optional[str] = None
    policy_version: int = 1


def evaluate_policy(policy: OrgPolicy, action: PolicyAction) -> PolicyDecision:
    """Pure decision: does `policy` permit `action`? One evaluator for all services."""

    def deny(clause: str, reason: str) -> PolicyDecision:
        return PolicyDecision(
            allowed=False,
            decision="deny",
            action_kind=action.kind,
            clause=clause,
            reason=reason,
            policy_version=policy.policy_version,
        )

    if action.kind == "spend":
        # OrgPolicy.max_spend_usd is a coarse per-action governance ceiling only.
        # Hierarchical feature/actor/team/workspace budgets defer to FinOps reserve.
        if (
            policy.max_spend_usd is not None
            and action.cost_usd is not None
            and action.cost_usd > policy.max_spend_usd
        ):
            return deny(
                "max_spend_usd",
                f"action cost ${action.cost_usd} exceeds org cap ${policy.max_spend_usd}",
            )
        if action.finops is not None and not action.finops.allowed:
            level = (action.finops.level_blocked or "budget").strip()
            dim = (action.finops.dimension_id or "").strip()
            window = (action.finops.window_blocked or "").strip()
            detail_parts = [p for p in (level, dim, window) if p]
            detail = " · ".join(detail_parts)
            base = action.finops.reason or "FinOps budget reserve denied"
            reason = f"{base} ({detail})" if detail else base
            return deny("finops_reserve", reason)
    elif action.kind == "external_send":
        if policy.require_approval_for_external_send and not action.approved:
            return deny(
                "require_approval_for_external_send",
                "external send requires an approved gate",
            )
    elif action.kind == "code_merge":
        if policy.require_security_review_for_merge and not action.security_reviewed:
            return deny(
                "require_security_review_for_merge",
                "code merge requires a passing security review",
            )
    elif action.kind == "memory_write":
        if policy.require_citation_for_memory_write and not action.has_citation:
            return deny(
                "require_citation_for_memory_write",
                "memory write requires a citation/source reference",
            )

    return PolicyDecision(
        allowed=True,
        decision="allow",
        action_kind=action.kind,
        policy_version=policy.policy_version,
    )


def build_policy_decision_event(
    policy: OrgPolicy,
    action: PolicyAction,
    decision: PolicyDecision,
    **extra: Any,
) -> "Any":
    """Build the canonical `policy.decision` KazenEvent — the one unified audit record.

    Imports KazenEvent lazily to avoid a circular import (``__init__`` imports this
    module). Returns a real KazenEvent so every service writes the same audit shape.
    """
    from kazen_event_schema import KazenEvent  # lazy: circular-import safe

    payload: Dict[str, Any] = {
        "action_kind": action.kind,
        "decision": decision.decision,
        "clause": decision.clause,
        "reason": decision.reason,
        "policy_version": policy.policy_version,
    }
    return KazenEvent(
        org_id=action.org_id or policy.org_id,
        surface=action.surface or "kazenai-platform",
        run_id=action.run_id,
        root_run_id=action.root_run_id,
        event_type="policy.decision",
        gate_decision="approve" if decision.allowed else "deny",
        payload=payload,
        **extra,
    )


def validate_governance_payload(event_type: str, payload: Dict[str, Any]) -> None:
    """Validate a governance event payload against its typed spec."""
    if event_type == "policy.decision":
        PolicyDecisionPayload.model_validate(payload)
