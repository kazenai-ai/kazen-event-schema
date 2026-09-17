"""Tests for typed payload validation in kazen_event_schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kazen_event_schema import (
    ContextCompactionPayload,
    FinOpsBudgetPayload,
    FinOpsPayload,
    GateDecisionPayload,
    KNOWN_EVENT_TYPES,
    ModelCallPayload,
    RunLifecyclePayload,
    ToolCallPayload,
    ToolRepairPayload,
    UsagePayload,
    validate_kazen_event,
    validate_payload,
)


# ---------------------------------------------------------------------------
# validate_payload() unit tests
# ---------------------------------------------------------------------------

def test_finops_budget_reserve_payload() -> None:
    validate_payload(
        "finops.budget.reserve",
        {"allowed": True, "model": "gpt-4o-mini", "reserved_cost_usd": 0.01},
    )


def test_finops_budget_denied_payload() -> None:
    validate_payload(
        "finops.budget.denied",
        {"allowed": False, "reason": "budget exhausted", "model": "gpt-4o-mini"},
    )


def test_finops_budget_denied_hierarchical_payload() -> None:
    validate_payload(
        "finops.budget.denied",
        {
            "allowed": False,
            "reason": "feature daily cap exceeded",
            "model": "gpt-4o-mini",
            "feature": "support-bot",
            "actor_id": "alice@acme",
            "level_blocked": "feature",
            "dimension": "feature",
            "dimension_id": "support-bot",
            "window_blocked": "daily",
        },
    )


def test_finops_budget_denied_hierarchy_levels_normalize_case() -> None:
    p = FinOpsBudgetPayload(
        allowed=False,
        level_blocked="FEATURE",
        dimension="Actor",
        dimension_id="bob@acme",
        window_blocked="monthly",
        actor_id="bob@acme",
    )
    assert p.level_blocked == "feature"
    assert p.dimension == "actor"


def test_finops_budget_denied_invalid_dimension_rejected() -> None:
    with pytest.raises(ValidationError):
        FinOpsBudgetPayload(allowed=False, dimension="workspace_id")


def test_finops_budget_denied_legacy_extra_fields_allowed() -> None:
    validate_payload(
        "finops.budget.denied",
        {
            "allowed": False,
            "reason": "budget exhausted",
            "window_blocked": "daily",
            "custom_trace": "ok",
        },
    )


def test_growthops_critic_verdict_event_is_registered() -> None:
    assert "growthops.critic.verdict" in KNOWN_EVENT_TYPES
    validate_kazen_event(
        {
            "schema_version": "1.2",
            "ts_ms": 1,
            "event_id": "critic-verdict-1",
            "org_id": "org-a",
            "workspace_id": "default",
            "project_id": "default",
            "surface": "kazenai-agent-growthops",
            "agent_id": "metrics_briefing",
            "agent_role": "growthops",
            "run_id": "run-1",
            "step_id": "critic",
            "event_type": "growthops.critic.verdict",
            "cost_quality_score": 0.82,
            "payload": {"agent_type": "metrics_briefing", "critic": {"score": 4}},
        },
        strict=True,
    )


def test_finops_budget_payload_model_class() -> None:
    p = FinOpsBudgetPayload(
        allowed=False,
        feature="support-bot",
        actor_id="apikey:550e8400-e29b-41d4-a716-446655440000",
        level_blocked="actor",
        dimension="actor",
        dimension_id="apikey:550e8400-e29b-41d4-a716-446655440000",
        window_blocked="monthly",
        projected_cost_usd=0.05,
    )
    assert p.level_blocked == "actor"
    assert p.dimension_id.startswith("apikey:")


def test_model_call_payload_valid() -> None:
    validate_payload("model.call", {"model": "claude-opus-4-7", "prompt_hash": "abc123"})


def test_model_call_payload_empty_allowed() -> None:
    # Empty payload is valid — all fields are optional
    validate_payload("model.call", {})


def test_model_call_payload_extra_fields_allowed() -> None:
    # extra="allow" means unknown fields pass through
    validate_payload("model.call", {"model": "gpt-4o", "custom_field": "ok"})


def test_model_call_payload_cache_fields() -> None:
    validate_payload(
        "model.call",
        {
            "model": "deepseek/deepseek-v3",
            "routing_profile": "deepseek",
            "model_tier": "flash",
            "cache_read_tokens": 12000,
            "cache_write_tokens": 800,
            "cache_hit_ratio": 0.94,
        },
    )


def test_tool_repair_payload_valid() -> None:
    validate_payload(
        "tool.repair.applied",
        {"scavenged": 2, "truncations_fixed": 1, "storms_broken": 0},
    )


def test_context_tool_result_compacted_payload() -> None:
    validate_payload(
        "context.tool_result_compacted",
        {"results_shrunk": 3, "tokens_saved_est": 4500, "turn_index": 2},
    )


def test_tool_call_payload_valid() -> None:
    validate_payload("tool.call", {"tool_name": "edit_file", "args_hash": "deadbeef"})


def test_mcp_call_uses_tool_call_validator() -> None:
    validate_payload("mcp.call", {"tool_name": "search_memory"})


def test_gate_decision_payload_valid() -> None:
    validate_payload(
        "gate.decision",
        {"gate_type": "gate_1", "decision": "approve", "reason": "budget ok"},
    )


def test_gate_decision_with_brain_trace_node_id() -> None:
    validate_payload(
        "gate.decision",
        {"gate_type": "gate_0", "brain_trace_node_id": "node-abc"},
    )


def test_run_started_payload() -> None:
    validate_payload("run.started", {"task_summary": "Add pagination to users API"})


def test_run_failed_payload() -> None:
    validate_payload("run.failed", {"error_type": "TimeoutError", "error_message": "timed out"})


def test_finops_circuit_breaker_payload() -> None:
    validate_payload(
        "finops.circuit_breaker.opened",
        {"threshold_usd": 5.0, "current_usd": 5.12, "reason": "budget exceeded"},
    )


def test_usage_recorded_payload() -> None:
    validate_payload(
        "usage.recorded",
        {"module": "workflow_runtime", "meter": "workflow_run", "quantity": 2, "cost_cents": 15, "source_service": "platform"},
    )


def test_unknown_event_type_passes_without_validation() -> None:
    # No validator registered for unknown types — always passes
    validate_payload("some.custom.event", {"any_field": "any_value"})


def test_llm_call_uses_model_call_validator() -> None:
    # llm.call is a legacy alias — should resolve to ModelCallPayload
    validate_payload("llm.call", {"model": "gpt-4"})


# ---------------------------------------------------------------------------
# validate_kazen_event() with validate_payload_contents=True
# ---------------------------------------------------------------------------

_BASE_EVENT = {
    "event_type": "model.call",
    "ts_ms": 1700000000000,
    "event_id": "evt-00000001",
    "org_id": "test-org",
    "project_id": "proj-1",
    "surface": "test",
    "agent_id": "agent-1",
    "run_id": "run-1",
    "step_id": "step-1",
}


def test_validate_kazen_event_with_valid_payload() -> None:
    ev = validate_kazen_event(
        {**_BASE_EVENT, "payload": {"model": "claude-sonnet-4-6"}},
        validate_payload_contents=True,
    )
    assert ev.event_type == "model.call"


def test_validate_kazen_event_payload_validation_off_by_default() -> None:
    # Invalid payload but validate_payload_contents defaults to False — no error
    ev = validate_kazen_event(
        {**_BASE_EVENT, "event_type": "gate.decision", "payload": {"decision": 999}},
    )
    assert ev.event_type == "gate.decision"


def test_validate_kazen_event_payload_validation_catches_type_error() -> None:
    with pytest.raises(ValidationError):
        validate_kazen_event(
            {**_BASE_EVENT, "event_type": "finops.circuit_breaker.opened",
             "payload": {"threshold_usd": "not-a-float"}},
            validate_payload_contents=True,
        )


def test_validate_kazen_event_empty_payload_skips_validation() -> None:
    # Empty payload dict should not trigger validation
    ev = validate_kazen_event(
        {**_BASE_EVENT, "payload": {}},
        validate_payload_contents=True,
    )
    assert ev.payload == {}


# ---------------------------------------------------------------------------
# Typed payload class direct construction
# ---------------------------------------------------------------------------

def test_model_call_payload_model_class() -> None:
    p = ModelCallPayload(
        model="deepseek/deepseek-v3",
        routing_profile="deepseek",
        cache_hit_ratio=0.9,
    )
    assert p.routing_profile == "deepseek"


def test_tool_repair_payload_model_class() -> None:
    p = ToolRepairPayload(scavenged=1, storms_broken=2)
    assert p.storms_broken == 2


def test_context_compaction_payload_model_class() -> None:
    p = ContextCompactionPayload(results_shrunk=5, tokens_saved_est=1000)
    assert p.results_shrunk == 5


def test_model_call_payload_model_class_legacy() -> None:
    p = ModelCallPayload(model="claude-opus-4-7", prompt_hash="abc")
    assert p.model == "claude-opus-4-7"


def test_gate_decision_payload_model_class() -> None:
    p = GateDecisionPayload(gate_type="gate_2", decision="deny", reason="cost too high")
    assert p.decision == "deny"


def test_finops_payload_model_class() -> None:
    p = FinOpsPayload(threshold_usd=5.0, current_usd=5.5)
    assert p.current_usd == 5.5


def test_usage_payload_model_class() -> None:
    p = UsagePayload(module="brain", meter="brain_node", quantity=4)
    assert p.quantity == 4
