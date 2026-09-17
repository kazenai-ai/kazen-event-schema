"""Loop 31 P3-2 proof — inter-agent mesh: Builder→Brain traced + budgeted."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SPINE = Path(__file__).resolve().parents[1]
_KAZEN = _SPINE.parent
if str(_SPINE) not in sys.path:
    sys.path.insert(0, str(_SPINE))

from kazen_event_schema import (  # noqa: E402
    BudgetDenied,
    InterAgentMesh,
    McpMeshSession,
    validate_kazen_event,
)
from kazen_event_schema.mcp_mesh import build_inter_agent_call_event  # noqa: E402


def _load_builder_mesh_router() -> ModuleType:
    path = _KAZEN / "kazenai-agent-builder" / "integrations" / "mesh_router.py"
    spec = importlib.util.spec_from_file_location("builder_mesh_router", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    builder_root = str(_KAZEN / "kazenai-agent-builder")
    if builder_root not in sys.path:
        sys.path.append(builder_root)
    spec.loader.exec_module(mod)
    return mod


ORG = "org-a-mesh"
ROOT = "root-mesh-p32"


def _handlers(brain_result: dict, finops_allowed: bool = True):
    def brain(tool, org, args):
        return brain_result

    def finops(tool, org, args):
        if not finops_allowed:
            return {"allowed": False, "reason": "org_budget_exhausted"}
        return {"allowed": True, "reason": "ok"}

    return {"brain": brain, "finops": finops}


def test_inter_agent_invoke_reserves_budget_then_calls_brain() -> None:
    session = McpMeshSession(org_id=ORG, root_run_id=ROOT, handlers=_handlers({"ok": True, "recall": {"context_pack": "SLA 99.9%"}}))
    mesh = InterAgentMesh(caller="builder", org_id=ORG, root_run_id=ROOT, session=session, reserve_usd=0.02)

    out = mesh.invoke("brain", "recall", {"query": "SLA?", "top_k": 5})
    assert out["recall"]["context_pack"] == "SLA 99.9%"

    # finops reserve + brain recall (session) + inter-agent audit
    assert len(session.events) >= 2
    assert session.events[0]["payload"]["tool_name"] == "finops.budget_reserve"
    inter = mesh.events[-1]
    validate_kazen_event(inter, strict=True)
    assert inter["root_run_id"] == ROOT
    assert inter["payload"]["inter_agent"] is True
    assert inter["payload"]["caller_service"] == "builder"
    assert inter["payload"]["callee_service"] == "brain"
    assert inter["payload"]["budget_reserved_usd"] == 0.02
    assert inter["surface"] == "kazenai-agent-builder"


def test_inter_agent_blocked_when_budget_exhausted() -> None:
    session = McpMeshSession(org_id=ORG, root_run_id=ROOT, handlers=_handlers({}, finops_allowed=False))
    mesh = InterAgentMesh(caller="builder", org_id=ORG, root_run_id=ROOT, session=session)

    with pytest.raises(BudgetDenied):
        mesh.invoke("brain", "recall", {"query": "x"})

    assert mesh.events[-1]["payload"]["allowed"] is False


def test_builder_retrieve_context_routes_through_mesh() -> None:
    mesh_router = _load_builder_mesh_router()
    brain_payload = {"ok": True, "recall": {"context_pack": "Enterprise retention is 90 days.", "citations": []}}
    lineage: list[dict] = []

    with mesh_router.mesh_run(
        org_id=ORG,
        root_run_id=ROOT,
        brain_handler=lambda t, o, a: brain_payload,
        finops_handler=lambda t, o, a: {"allowed": True},
        event_sink=lineage.append,
    ):
        result = mesh_router.try_mesh_brain_recall("retention policy?", org_id=ORG, run_id=ROOT, caller="planner")

    assert result is not None
    assert "90 days" in (result.get("context_pack") or result.get("recall", {}).get("context_pack", ""))

    # lineage: budget reserve + brain recall + inter-agent audit
    assert len(lineage) >= 1
    inter_events = [e for e in lineage if e.get("payload", {}).get("inter_agent")]
    assert inter_events
    assert all(e["root_run_id"] == ROOT for e in lineage)
    assert all(e["org_id"] == ORG for e in lineage)
    assert inter_events[0]["payload"]["caller_service"] == "builder"
    assert inter_events[0]["payload"]["callee_service"] == "brain"


def test_cross_tenant_org_mismatch_on_inter_agent() -> None:
    from kazen_event_schema import OrgMismatch

    session = McpMeshSession(org_id=ORG, root_run_id=ROOT, handlers=_handlers({"ok": True}))
    mesh = InterAgentMesh(caller="builder", org_id=ORG, root_run_id=ROOT, session=session)

    with pytest.raises(OrgMismatch):
        mesh.invoke("brain", "recall", {"query": "x", "org_id": "org-b-leak"})


def test_inter_agent_event_validates_on_spine() -> None:
    ev = build_inter_agent_call_event(
        org_id=ORG,
        root_run_id=ROOT,
        caller="builder",
        callee="brain",
        tool_name="recall",
        arguments={"query": "q"},
        allowed=True,
        budget_reserved_usd=0.01,
    )
    validate_kazen_event(ev, strict=True)
    assert ev["event_type"] == "mcp.call"
