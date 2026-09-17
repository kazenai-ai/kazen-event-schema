"""Tests for Conductor-compatible orchestration event types (Loop 24 P0-1)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from kazen_event_schema import (
    ORCHESTRATION_EVENT_TYPES,
    OrchestrationRole,
    OrchestrationStepPayload,
    OrchestrationWorkflow,
    OrchestrationWorkflowPlannedPayload,
    OrchestrationWorkflowRevisedPayload,
    KazenEvent,
    is_known_event_type,
    orchestration_workflow_round_trip,
    validate_kazen_event,
    validate_orchestration_payload,
    validate_payload,
    workflow_to_planned_payload,
)


_SAMPLE_WORKFLOW = OrchestrationWorkflow(
    workflow_id="wf-abc123",
    model_id=["bedrock_claude", "deepseek", "bedrock_claude"],
    subtasks=[
        "Explore failing test and locate root cause",
        "Apply SEARCH/REPLACE patch to fix import",
        "Run FAIL_TO_PASS pytest and verify oracle",
    ],
    access_list=[[], [0], [0, 1]],
    roles=["thinker", "worker", "verifier"],
    lineage_id="lineage-loop23-001",
)


def test_orchestration_event_types_registered() -> None:
    for event_type in ORCHESTRATION_EVENT_TYPES:
        assert is_known_event_type(event_type)


def test_orchestration_role_enum_values() -> None:
    assert OrchestrationRole.THINKER.value == "thinker"
    assert OrchestrationRole.WORKER.value == "worker"
    assert OrchestrationRole.VERIFIER.value == "verifier"


def test_orchestration_workflow_json_round_trip() -> None:
    restored = orchestration_workflow_round_trip(_SAMPLE_WORKFLOW)
    assert restored == _SAMPLE_WORKFLOW
    assert restored.model_id == ["bedrock_claude", "deepseek", "bedrock_claude"]
    assert restored.access_list == [[], [0], [0, 1]]
    assert restored.lineage_id == "lineage-loop23-001"


def test_orchestration_workflow_roles_length_validation() -> None:
    with pytest.raises(ValidationError):
        OrchestrationWorkflow(
            workflow_id="wf-bad",
            model_id=["a", "b"],
            roles=["thinker"],
        )


def test_workflow_to_planned_payload() -> None:
    payload = workflow_to_planned_payload(_SAMPLE_WORKFLOW)
    assert payload["workflow_id"] == "wf-abc123"
    assert payload["roles"] == ["thinker", "worker", "verifier"]
    assert payload["lineage_id"] == "lineage-loop23-001"


def test_validate_orchestration_workflow_planned_payload() -> None:
    payload = workflow_to_planned_payload(_SAMPLE_WORKFLOW)
    validate_orchestration_payload("orchestration.workflow.planned", payload)
    validate_payload("orchestration.workflow.planned", payload)


def test_validate_orchestration_step_started_payload() -> None:
    step = {
        "workflow_id": "wf-abc123",
        "step_index": 1,
        "worker_model": "deepseek",
        "tri_role": "worker",
        "subtask": "Apply SEARCH/REPLACE patch to fix import",
        "lineage_id": "lineage-loop23-001",
    }
    validate_orchestration_payload("orchestration.step.started", step)
    validate_payload("orchestration.step.started", step)


def test_validate_orchestration_step_completed_payload() -> None:
    step = {
        "workflow_id": "wf-abc123",
        "step_index": 2,
        "worker_model": "bedrock_claude",
        "tri_role": "verifier",
        "subtask": "Run FAIL_TO_PASS pytest",
        "cost_usd": 0.0042,
    }
    validate_orchestration_payload("orchestration.step.completed", step)
    validate_payload("orchestration.step.completed", step)


def test_validate_orchestration_workflow_revised_payload() -> None:
    revised = {
        "workflow_id": "wf-rev-002",
        "parent_workflow_id": "wf-abc123",
        "model_id": ["deepseek", "bedrock_claude"],
        "subtasks": ["Retry patch with format repair", "Re-verify oracle"],
        "access_list": [[0], [0, 1]],
        "roles": ["worker", "verifier"],
        "revision_depth": 1,
        "reason": "verifier_revise",
    }
    validate_orchestration_payload("orchestration.workflow.revised", revised)
    validate_payload("orchestration.workflow.revised", revised)


def test_kazen_event_orchestration_step_round_trip() -> None:
    raw = {
        "event_type": "orchestration.step.completed",
        "ts_ms": 1700000000000,
        "event_id": "evt-orch-0001",
        "org_id": "test-org",
        "project_id": "proj-1",
        "surface": "kazenai-agent-builder",
        "agent_id": "devagent",
        "run_id": "run-orch-1",
        "step_id": "step-2",
        "cost_usd": 0.0042,
        "payload": {
            "workflow_id": "wf-abc123",
            "step_index": 2,
            "worker_model": "bedrock_claude",
            "tri_role": "verifier",
            "subtask": "Run FAIL_TO_PASS pytest",
            "cost_usd": 0.0042,
        },
    }
    ev = validate_kazen_event(raw, strict=True, validate_payload_contents=True)
    wire = json.loads(ev.model_dump_json())
    ev2 = validate_kazen_event(wire, strict=True, validate_payload_contents=True)
    assert ev2.event_type == "orchestration.step.completed"
    assert ev2.payload["tri_role"] == "verifier"
    assert ev2.cost_usd == 0.0042


def test_kazen_event_workflow_planned_strict() -> None:
    raw = {
        "event_type": "orchestration.workflow.planned",
        "ts_ms": 1700000000000,
        "event_id": "evt-orch-plan",
        "org_id": "test-org",
        "project_id": "proj-1",
        "surface": "kazenai-gateway",
        "agent_id": "kazen-route",
        "run_id": "run-route-1",
        "payload": workflow_to_planned_payload(_SAMPLE_WORKFLOW),
    }
    ev = KazenEvent.model_validate(raw)
    assert ev.event_type == "orchestration.workflow.planned"
    assert len(ev.payload["model_id"]) == 3


def test_orchestration_step_invalid_tri_role() -> None:
    with pytest.raises(ValidationError):
        OrchestrationStepPayload.model_validate(
            {
                "workflow_id": "wf-x",
                "step_index": 0,
                "tri_role": "oracle",
            }
        )


def test_orchestration_workflow_revised_requires_parent() -> None:
    with pytest.raises(ValidationError):
        OrchestrationWorkflowRevisedPayload.model_validate(
            {
                "workflow_id": "wf-rev",
                "parent_workflow_id": "",
                "revision_depth": 0,
            }
        )


def test_orchestration_reward_recorded_payload() -> None:
    from kazen_event_schema.orchestration import OrchestrationRewardRecordedPayload

    payload = OrchestrationRewardRecordedPayload.model_validate(
        {
            "workflow_id": "wf-r",
            "run_id": "run-r",
            "scalar": 0.75,
            "components": {
                "resolved": 1.0,
                "critic_pass": 0.5,
                "within_budget": 1.0,
                "grounded": 1.0,
                "human_approved": 0.0,
            },
            "weights": {"resolved": 0.35, "critic_pass": 0.2, "within_budget": 0.15, "grounded": 0.15, "human_approved": 0.15},
        }
    )
    assert payload.scalar == 0.75
    validate_orchestration_payload("orchestration.reward.recorded", payload.model_dump())
    assert "orchestration.reward.recorded" in ORCHESTRATION_EVENT_TYPES
