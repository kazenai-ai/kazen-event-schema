"""Organization spend policy: one evaluator, one canonical policy.decision event."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kazen_event_schema import (
    FinOpsReserveContext,
    OrgPolicy,
    PolicyAction,
    build_policy_decision_event,
    evaluate_policy,
    is_known_event_type,
    validate_kazen_event,
)


def test_spend_over_the_org_ceiling_is_denied() -> None:
    policy = OrgPolicy(org_id="org-a", max_spend_usd=1.00)
    decision = evaluate_policy(policy, PolicyAction(kind="spend", org_id="org-a", cost_usd=5.0))
    assert decision.allowed is False
    assert decision.decision == "deny"
    assert decision.clause == "max_spend_usd"


def test_spend_within_the_org_ceiling_is_allowed() -> None:
    policy = OrgPolicy(org_id="org-a", max_spend_usd=1.00)
    decision = evaluate_policy(policy, PolicyAction(kind="spend", org_id="org-a", cost_usd=0.50))
    assert decision.allowed is True
    assert decision.decision == "allow"


def test_only_spend_actions_exist() -> None:
    with pytest.raises(ValidationError):
        PolicyAction(kind="external_send", org_id="org-a")


def test_no_cap_means_no_spend_block() -> None:
    policy = OrgPolicy(org_id="org-a", max_spend_usd=None)
    decision = evaluate_policy(policy, PolicyAction(kind="spend", cost_usd=10_000.0))
    assert decision.allowed is True


def test_org_ceiling_blocks_spend_before_finops() -> None:
    """max_spend_usd is the org ceiling; it is checked before the FinOps reserve outcome."""
    policy = OrgPolicy(org_id="org-a", max_spend_usd=1.00)
    action = PolicyAction(
        kind="spend",
        org_id="org-a",
        surface="kazenai-agent-finops",
        cost_usd=5.0,
        finops=FinOpsReserveContext(allowed=True),
    )
    decision = evaluate_policy(policy, action)
    assert decision.allowed is False
    assert decision.clause == "max_spend_usd"


def test_feature_cap_blocks_via_finops_reserve_clause() -> None:
    """Hierarchical feature budgets are decided by the FinOps reserve, not OrgPolicy."""
    policy = OrgPolicy(org_id="org-a", max_spend_usd=None)
    action = PolicyAction(
        kind="spend",
        org_id="org-a",
        surface="kazenai-agent-finops",
        workspace_id="prod",
        feature="support-bot",
        cost_usd=0.50,
        finops=FinOpsReserveContext(
            allowed=False,
            reason="feature budget exceeded",
            level_blocked="feature",
            dimension_id="support-bot",
            window_blocked="daily",
        ),
    )
    decision = evaluate_policy(policy, action)
    assert decision.allowed is False
    assert decision.decision == "deny"
    assert decision.clause == "finops_reserve"
    assert "support-bot" in (decision.reason or "")
    assert "feature" in (decision.reason or "")


def test_finops_allow_with_no_org_ceiling_permits_spend() -> None:
    policy = OrgPolicy(org_id="org-a", max_spend_usd=None)
    action = PolicyAction(
        kind="spend",
        cost_usd=0.50,
        finops=FinOpsReserveContext(allowed=True),
    )
    assert evaluate_policy(policy, action).allowed is True


def test_decision_emits_one_canonical_audit_event() -> None:
    policy = OrgPolicy(org_id="org-a", policy_version=7, max_spend_usd=1.00)
    assert is_known_event_type("policy.decision")

    action = PolicyAction(
        kind="spend",
        org_id="org-a",
        surface="kazenai-agent-finops",
        run_id="run-9",
        root_run_id="root-run-100",
        cost_usd=5.0,
    )
    decision = evaluate_policy(policy, action)
    event = build_policy_decision_event(policy, action, decision)

    validated = validate_kazen_event(event.model_dump(), strict=True, validate_payload_contents=True)
    assert validated.event_type == "policy.decision"
    assert validated.org_id == "org-a"
    assert validated.surface == "kazenai-agent-finops"
    assert validated.gate_decision == "deny"
    assert validated.root_run_id == "root-run-100"
    assert validated.payload["clause"] == "max_spend_usd"
    assert validated.payload["decision"] == "deny"
    assert validated.payload["policy_version"] == 7
