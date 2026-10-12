"""Every event type the kazenai SDK emits must pass strict validation."""

import pytest

from kazen_event_schema import KNOWN_EVENT_TYPES, validate_kazen_event

# Keep in sync with kazenai-core; core's test_emitted_event_types_registered
# scans its own source and fails if it emits a type missing from this registry.
CORE_EMITTED = [
    "finops.budget.denied",
    "finops.budget.reserve",
    "finops.circuit_breaker.opened",
    "finops.loop.anomaly",
    "finops.trajectory",
    "model.call",
    "tool.call",
    "workflow.end",
    "workflow.error",
    "workflow.start",
    "workflow.step",
    "workflow.suspend",
]


@pytest.mark.parametrize("event_type", CORE_EMITTED)
def test_core_emitted_type_is_registered_and_strict_valid(event_type: str) -> None:
    assert event_type in KNOWN_EVENT_TYPES
    ev = validate_kazen_event(
        {"org_id": "org", "agent_id": "agent", "event_type": event_type, "run_id": "run-1"},
        strict=True,
    )
    assert ev.event_type == event_type
