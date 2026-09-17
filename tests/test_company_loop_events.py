"""Tests for company operating loop event types (Loop 23 P0-1)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from kazen_event_schema import (
    COMPANY_LOOP_EVENT_TYPES,
    CompanyLoopRecord,
    KazenEvent,
    company_loop_record_round_trip,
    is_known_event_type,
    record_to_goal_created_payload,
    validate_company_loop_payload,
    validate_kazen_event,
    validate_payload,
)


_SAMPLE_RECORD = CompanyLoopRecord(
    lineage_id="lineage-cl-001",
    org_id="org-acme",
    goal_id="goal-q2-pipeline",
    owner_agent="growthops.sales_conversation",
    run_id="run-gr-42",
    approval_id="appr-send-7",
    outcome="approved",
    memory_node_ids=["node-fact-101", "node-fact-102"],
)


def test_company_loop_event_types_registered() -> None:
    for event_type in COMPANY_LOOP_EVENT_TYPES:
        assert is_known_event_type(event_type)


def test_company_loop_record_json_round_trip() -> None:
    restored = company_loop_record_round_trip(_SAMPLE_RECORD)
    assert restored == _SAMPLE_RECORD
    assert restored.memory_node_ids == ["node-fact-101", "node-fact-102"]


def test_company_loop_record_requires_lineage_and_org() -> None:
    with pytest.raises(ValidationError):
        CompanyLoopRecord(lineage_id="", org_id="org-x")
    with pytest.raises(ValidationError):
        CompanyLoopRecord(lineage_id="lineage-x", org_id="")


def test_record_to_goal_created_payload() -> None:
    payload = record_to_goal_created_payload(
        _SAMPLE_RECORD,
        title="Close Q2 pipeline gap",
        priority="P0",
    )
    assert payload["lineage_id"] == "lineage-cl-001"
    assert payload["goal_id"] == "goal-q2-pipeline"
    assert payload["owner_agent"] == "growthops.sales_conversation"
    validate_company_loop_payload("company.goal.created", payload)
    validate_payload("company.goal.created", payload)


def test_validate_company_run_started_payload() -> None:
    payload = {
        "lineage_id": "lineage-cl-001",
        "org_id": "org-acme",
        "goal_id": "goal-q2-pipeline",
        "owner_agent": "growthops.outreach_research",
        "run_id": "run-gr-99",
        "surface": "kazenai-agent-growthops",
        "task_summary": "ICP research for 3 accounts",
    }
    validate_company_loop_payload("company.run.started", payload)
    validate_payload("company.run.started", payload)


def test_validate_company_approval_pending_payload() -> None:
    payload = {
        "lineage_id": "lineage-cl-001",
        "org_id": "org-acme",
        "goal_id": "goal-q2-pipeline",
        "run_id": "run-gr-42",
        "approval_id": "appr-send-7",
        "blocker_id": "blk-approval-7",
        "blocker_kind": "approval",
        "approval_kind": "outreach_send",
        "impact_preview": "Send follow-up to acme@example.com",
    }
    validate_company_loop_payload("company.approval.pending", payload)
    validate_payload("company.approval.pending", payload)


def test_validate_company_outcome_recorded_payload() -> None:
    payload = {
        "lineage_id": "lineage-cl-001",
        "org_id": "org-acme",
        "goal_id": "goal-q2-pipeline",
        "run_id": "run-gr-42",
        "approval_id": "appr-send-7",
        "outcome": "approved",
        "recorded_by": "operator@acme.com",
    }
    validate_company_loop_payload("company.outcome.recorded", payload)
    validate_payload("company.outcome.recorded", payload)


def test_validate_company_memory_committed_payload() -> None:
    payload = {
        "lineage_id": "lineage-cl-001",
        "org_id": "org-acme",
        "goal_id": "goal-q2-pipeline",
        "run_id": "run-gr-42",
        "memory_node_ids": ["node-fact-101"],
        "write_id": "mw-abc",
        "lifecycle_stage": "candidate_fact",
    }
    validate_company_loop_payload("company.memory.committed", payload)
    validate_payload("company.memory.committed", payload)


def test_kazen_event_company_run_started_round_trip() -> None:
    raw = {
        "event_type": "company.run.started",
        "ts_ms": 1700000000000,
        "event_id": "evt-cl-run-001",
        "org_id": "org-acme",
        "project_id": "general",
        "surface": "kazenai-agent-growthops",
        "agent_id": "growthops.outreach_research",
        "run_id": "run-gr-99",
        "payload": {
            "lineage_id": "lineage-cl-001",
            "org_id": "org-acme",
            "goal_id": "goal-q2-pipeline",
            "owner_agent": "growthops.outreach_research",
            "run_id": "run-gr-99",
            "surface": "kazenai-agent-growthops",
            "task_summary": "ICP research for 3 accounts",
        },
    }
    ev = validate_kazen_event(raw, strict=True, validate_payload_contents=True)
    wire = json.loads(ev.model_dump_json())
    ev2 = validate_kazen_event(wire, strict=True, validate_payload_contents=True)
    assert ev2.event_type == "company.run.started"
    assert ev2.payload["lineage_id"] == "lineage-cl-001"
    assert ev2.run_id == "run-gr-99"


def test_kazen_event_company_memory_committed_strict() -> None:
    raw = {
        "event_type": "company.memory.committed",
        "ts_ms": 1700000000000,
        "event_id": "evt-cl-mem-001",
        "org_id": "org-acme",
        "project_id": "general",
        "surface": "kazenai-agent-brain",
        "agent_id": "brain.ingest",
        "run_id": "run-gr-42",
        "touched_node_ids": ["node-fact-101"],
        "payload": {
            "lineage_id": "lineage-cl-001",
            "org_id": "org-acme",
            "goal_id": "goal-q2-pipeline",
            "run_id": "run-gr-42",
            "memory_node_ids": ["node-fact-101"],
            "write_id": "mw-abc",
            "lifecycle_stage": "candidate_fact",
        },
    }
    ev = KazenEvent.model_validate(raw)
    assert ev.event_type == "company.memory.committed"
    assert ev.touched_node_ids == ["node-fact-101"]


def test_company_outcome_invalid_literal() -> None:
    with pytest.raises(ValidationError):
        validate_company_loop_payload(
            "company.outcome.recorded",
            {
                "lineage_id": "lineage-cl-001",
                "org_id": "org-acme",
                "outcome": "maybe",
            },
        )


def test_full_lineage_event_sequence_payloads() -> None:
    """Contract: each lifecycle stage validates and shares lineage_id."""
    lineage_id = "lineage-cl-seq"
    org_id = "org-acme"
    goal_id = "goal-1"
    owner = "growthops.sales_conversation"
    run_id = "run-1"
    approval_id = "appr-1"

    stages = [
        (
            "company.goal.created",
            record_to_goal_created_payload(
                CompanyLoopRecord(
                    lineage_id=lineage_id,
                    org_id=org_id,
                    goal_id=goal_id,
                    owner_agent=owner,
                )
            ),
        ),
        (
            "company.run.started",
            {
                "lineage_id": lineage_id,
                "org_id": org_id,
                "goal_id": goal_id,
                "owner_agent": owner,
                "run_id": run_id,
            },
        ),
        (
            "company.approval.pending",
            {
                "lineage_id": lineage_id,
                "org_id": org_id,
                "goal_id": goal_id,
                "run_id": run_id,
                "approval_id": approval_id,
                "blocker_kind": "approval",
            },
        ),
        (
            "company.outcome.recorded",
            {
                "lineage_id": lineage_id,
                "org_id": org_id,
                "goal_id": goal_id,
                "run_id": run_id,
                "approval_id": approval_id,
                "outcome": "approved",
            },
        ),
        (
            "company.memory.committed",
            {
                "lineage_id": lineage_id,
                "org_id": org_id,
                "goal_id": goal_id,
                "run_id": run_id,
                "memory_node_ids": ["node-1"],
            },
        ),
    ]
    for event_type, payload in stages:
        assert payload["lineage_id"] == lineage_id
        validate_company_loop_payload(event_type, payload)
        validate_payload(event_type, payload)
