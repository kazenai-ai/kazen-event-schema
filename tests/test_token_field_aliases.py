"""Canonical tokens=17 normalization (already correct here)."""

from __future__ import annotations

from kazen_event_schema import KazenEvent


def test_canonical_tokens_17_normalizes_tokens_used() -> None:
    event = KazenEvent.model_validate(
        {
            "schema_version": "1.2",
            "ts_ms": 1_700_000_000_000,
            "event_id": "evt_p0_tokens17_canonical",
            "org_id": "org_p0",
            "workspace_id": "default",
            "project_id": "default",
            "surface": "kazenai-sdk",
            "agent_id": "agent_p0",
            "event_type": "model.call",
            "tokens": 17,
        }
    )
    assert event.tokens == 17
    assert event.tokens_used == 17
