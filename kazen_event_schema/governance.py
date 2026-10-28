"""Organization spend policy and its audit event.

`OrgPolicy.max_spend_usd` is a coarse per-action spend ceiling for an organization.
Hierarchical budgets (feature, actor, team, workspace) are decided by the Agent FinOps
reserve and passed in as `FinOpsReserveContext`. `evaluate_policy()` returns the
decision, and `build_policy_decision_event()` records it as one canonical
`policy.decision` KazenEvent.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

PolicyActionKind = Literal["spend"]

GOVERNANCE_EVENT_TYPES = frozenset({"policy.decision"})


class OrgPolicy(BaseModel):
    """An organization's spend policy."""

    model_config = ConfigDict(extra="allow")

    org_id: str = "local"
    policy_version: int = 1
    # None means "no cap"; a number caps per-action spend in USD.
    max_spend_usd: Optional[float] = None
    updated_at_ms: int = Field(default_factory=lambda: int(time.time() * 1000))


class PolicyAction(BaseModel):
    """A spend action a service wants to take, checked against OrgPolicy."""

    model_config = ConfigDict(extra="allow")

    kind: PolicyActionKind
    org_id: str = "local"
    surface: Optional[str] = None  # the service or SDK that emitted the action
    run_id: Optional[str] = None
    root_run_id: Optional[str] = None
    cost_usd: Optional[float] = None
    workspace_id: Optional[str] = None    # Agent FinOps workspace scope
    feature: Optional[str] = None         # Agent FinOps feature slug
    actor_id: Optional[str] = None        # Agent FinOps actor (from the principal)
    finops: Optional["FinOpsReserveContext"] = None  # hierarchical budget outcome


class FinOpsReserveContext(BaseModel):
    """Outcome of an Agent FinOps reserve; hierarchical budgets are decided there, not by OrgPolicy."""

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
    """Pure decision: does `policy` permit `action`?"""

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
