"""Loop 31 P0-2 — unified cross-product lineage fields on the canonical KazenEvent.

These guard that root_run_id / trace_id are first-class wire fields (the canonical
model is extra="forbid", so before P0-2 producers could not pass them at all) and
that self-rooting makes every event join-able by root_run_id.
"""

from __future__ import annotations

from kazen_event_schema import KazenEvent, validate_kazen_event


def test_lineage_fields_round_trip() -> None:
    ev = KazenEvent(
        org_id="org-a",
        workspace_id="ws-1",
        run_id="run-child",
        parent_run_id="run-parent",
        root_run_id="run-root",
        trace_id="trace-xyz",
        cost_usd=0.42,
        event_type="model.call",
    )
    restored = validate_kazen_event(ev.model_dump())
    assert restored.root_run_id == "run-root"
    assert restored.trace_id == "trace-xyz"
    assert restored.parent_run_id == "run-parent"
    assert restored.run_id == "run-child"
    assert restored.cost_usd == 0.42


def test_self_rooting_defaults_root_to_run_id() -> None:
    # A standalone run with no explicit root is its own root.
    ev = KazenEvent(org_id="org-a", run_id="run-solo", event_type="run.started")
    assert ev.root_run_id == "run-solo"


def test_explicit_root_is_not_overwritten() -> None:
    # A child run carrying its parent's root must keep it, not collapse to run_id.
    ev = KazenEvent(
        org_id="org-a",
        run_id="run-child",
        root_run_id="run-root",
        event_type="run.started",
    )
    assert ev.root_run_id == "run-root"
    assert ev.run_id == "run-child"


def test_no_run_id_leaves_root_none() -> None:
    ev = KazenEvent(org_id="org-a", event_type="kpi.snapshot")
    assert ev.run_id is None
    assert ev.root_run_id is None


def test_schema_version_unchanged() -> None:
    # Must stay 1.2 — Lens's require_v1 validator accepts only {1.0, 1.1, 1.2}.
    assert KazenEvent(org_id="org-a", event_type="run.started").schema_version == "1.2"
