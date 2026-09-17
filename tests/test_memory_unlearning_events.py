"""Spine validation for Brain P4-B memory audit events."""

from kazen_event_schema import (
    MemoryForgottenPayload,
    MemoryRecallBenchmarkPayload,
    validate_kazen_event,
    validate_payload,
)


def test_memory_forgotten_payload_validates():
    payload = {
        "node_id": "fact-1",
        "content_fingerprint": "abc123",
        "reason": "GDPR erasure",
        "requested_by": "dpo@company.com",
        "deleted": {"nodes": 1, "chunks": 1},
        "found": True,
    }
    validate_payload("memory.forgotten", payload)
    MemoryForgottenPayload.model_validate(payload)


def test_memory_recall_benchmark_payload_validates():
    payload = {
        "recall_before": 0.5,
        "recall_after": 0.75,
        "recall_lift": 0.25,
        "probe_count": 3,
    }
    validate_payload("memory.recall_benchmark", payload)
    MemoryRecallBenchmarkPayload.model_validate(payload)


def test_memory_forgotten_kazen_event_round_trip():
    ev = validate_kazen_event(
        {
            "event_type": "memory.forgotten",
            "org_id": "org-a",
            "agent_id": "brain.unlearning",
            "payload": {
                "node_id": "n1",
                "content_fingerprint": "fp",
                "reason": "erasure",
                "requested_by": "dpo@a.com",
                "deleted": {"nodes": 1},
                "found": True,
            },
        }
    )
    assert ev.event_type == "memory.forgotten"
    assert ev.payload["requested_by"] == "dpo@a.com"
