"""Loop 31 P0-2 — cross-service lineage proof (>=2 components, one shared root_run_id).

A single event dict carrying a shared root_run_id must validate through BOTH the
canonical kazen_event_schema and Lens's ingest schema, with the lineage fields
preserved by each. This is the cross-product proof the loop requires (not a
single-service mock). The canonical model is the source of truth; Lens's parallel
ingest model is aligned to it (it loads schema.py directly so the test does not
require Lens's full backend deps).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from kazen_event_schema import validate_kazen_event

# Locate Lens's ingest schema relative to the workspace root (../kazenai-agent-lens).
_LENS_SCHEMA = (
    Path(__file__).resolve().parents[2]
    / "kazenai-agent-lens"
    / "backend"
    / "agent_lens"
    / "schema.py"
)


def _load_lens_kazen_event():
    if not _LENS_SCHEMA.exists():
        pytest.skip(f"Lens schema not present at {_LENS_SCHEMA}")
    spec = importlib.util.spec_from_file_location("agent_lens_schema_under_test", _LENS_SCHEMA)
    if spec is None or spec.loader is None:
        pytest.skip("could not load Lens schema module")
    module = importlib.util.module_from_spec(spec)
    # Register before exec so pydantic can resolve the module's globalns when it
    # rebuilds the model's `from __future__ import annotations` string refs.
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover - env-dependent
        pytest.skip(f"Lens schema import failed in this interpreter: {exc}")
    return module.KazenEvent


# One event, emitted as if a Builder run that shares a root with its FinOps cost,
# Lens trace, and Brain writes.
SHARED_EVENT = {
    "schema_version": "1.2",
    "ts_ms": 1_700_000_000_000,
    "event_id": "evt-cross-0001",
    "org_id": "org-a",
    "workspace_id": "ws-1",
    "project_id": "proj-1",
    "surface": "kazenai-agent-builder",
    "agent_id": "devagent",
    "agent_role": "builder",
    "run_id": "run-builder-9",
    "parent_run_id": "run-orchestrator-1",
    "root_run_id": "root-run-100",
    "trace_id": "trace-abc-100",
    "cost_usd": 0.37,
    "event_type": "delivery.pr.created",
}


def test_canonical_preserves_shared_lineage() -> None:
    ev = validate_kazen_event(dict(SHARED_EVENT))
    assert ev.root_run_id == "root-run-100"
    assert ev.trace_id == "trace-abc-100"


def test_lens_ingest_preserves_shared_lineage() -> None:
    LensKazenEvent = _load_lens_kazen_event()
    ev = LensKazenEvent.model_validate(dict(SHARED_EVENT))
    assert ev.root_run_id == "root-run-100"
    assert ev.trace_id == "trace-abc-100"


def test_both_services_agree_on_root_run_id() -> None:
    LensKazenEvent = _load_lens_kazen_event()
    canonical = validate_kazen_event(dict(SHARED_EVENT))
    lens = LensKazenEvent.model_validate(dict(SHARED_EVENT))
    # The whole point of the spine: one root_run_id joins the run across products.
    assert canonical.root_run_id == lens.root_run_id == "root-run-100"
    assert canonical.trace_id == lens.trace_id == "trace-abc-100"
