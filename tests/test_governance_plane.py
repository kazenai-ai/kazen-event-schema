"""Loop 31 P1-2 — one org policy plane governs all five agents + one audit log.

Proves the cross-product claim at the shared-evaluator level: a SINGLE OrgPolicy
object decides the four governed action classes (one per enforcement surface:
FinOps spend, GrowthOps external-send, Builder code-merge, Brain memory-write), that
flipping a clause flips behaviour, and that every decision produces the same
canonical `policy.decision` KazenEvent (the unified audit log).
"""

from __future__ import annotations

from kazen_event_schema import (
    FinOpsReserveContext,
    OrgPolicy,
    PolicyAction,
    build_policy_decision_event,
    evaluate_policy,
    is_known_event_type,
    validate_kazen_event,
)


def _strict_policy() -> OrgPolicy:
    return OrgPolicy(
        org_id="org-a",
        policy_version=7,
        max_spend_usd=1.00,
        require_approval_for_external_send=True,
        require_security_review_for_merge=True,
        require_citation_for_memory_write=True,
    )


def test_one_policy_blocks_all_four_action_classes() -> None:
    policy = _strict_policy()

    blocked = {
        "spend": PolicyAction(kind="spend", org_id="org-a", surface="kazenai-agent-finops", cost_usd=5.0),
        "external_send": PolicyAction(kind="external_send", org_id="org-a", surface="kazenai-agent-growthops", approved=False),
        "code_merge": PolicyAction(kind="code_merge", org_id="org-a", surface="kazenai-agent-builder", security_reviewed=False),
        "memory_write": PolicyAction(kind="memory_write", org_id="org-a", surface="kazenai-agent-brain", has_citation=False),
    }
    for kind, action in blocked.items():
        decision = evaluate_policy(policy, action)
        assert decision.allowed is False, f"{kind} should be blocked"
        assert decision.decision == "deny"
        assert decision.clause is not None


def test_one_policy_allows_compliant_actions() -> None:
    policy = _strict_policy()
    allowed = [
        PolicyAction(kind="spend", org_id="org-a", cost_usd=0.50),
        PolicyAction(kind="external_send", org_id="org-a", approved=True),
        PolicyAction(kind="code_merge", org_id="org-a", security_reviewed=True),
        PolicyAction(kind="memory_write", org_id="org-a", has_citation=True),
    ]
    for action in allowed:
        decision = evaluate_policy(policy, action)
        assert decision.allowed is True
        assert decision.decision == "allow"


def test_flipping_a_clause_flips_behaviour() -> None:
    action = PolicyAction(kind="memory_write", org_id="org-a", has_citation=False)
    lenient = OrgPolicy(org_id="org-a", require_citation_for_memory_write=False)
    strict = OrgPolicy(org_id="org-a", require_citation_for_memory_write=True)
    assert evaluate_policy(lenient, action).allowed is True
    assert evaluate_policy(strict, action).allowed is False


def test_no_cap_means_no_spend_block() -> None:
    policy = OrgPolicy(org_id="org-a", max_spend_usd=None)
    decision = evaluate_policy(policy, PolicyAction(kind="spend", cost_usd=10_000.0))
    assert decision.allowed is True


def test_org_ceiling_blocks_spend_before_finops() -> None:
    """max_spend_usd is the org governance ceiling; checked before FinOps reserve."""
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
    """Hierarchical feature budgets defer to FinOps — not duplicated in OrgPolicy."""
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
    """Every clause's deny produces the SAME policy.decision KazenEvent shape."""
    policy = _strict_policy()
    assert is_known_event_type("policy.decision")

    action = PolicyAction(
        kind="code_merge",
        org_id="org-a",
        surface="kazenai-agent-builder",
        run_id="run-builder-9",
        root_run_id="root-run-100",
        security_reviewed=False,
    )
    decision = evaluate_policy(policy, action)
    event = build_policy_decision_event(policy, action, decision)

    # validates as a strict KazenEvent incl. typed payload — the one audit record.
    validated = validate_kazen_event(event.model_dump(), strict=True, validate_payload_contents=True)
    assert validated.event_type == "policy.decision"
    assert validated.org_id == "org-a"
    assert validated.surface == "kazenai-agent-builder"
    assert validated.gate_decision == "deny"
    assert validated.root_run_id == "root-run-100"  # audit joins to lineage (P1-1)
    assert validated.payload["clause"] == "require_security_review_for_merge"
    assert validated.payload["decision"] == "deny"
    assert validated.payload["policy_version"] == 7
