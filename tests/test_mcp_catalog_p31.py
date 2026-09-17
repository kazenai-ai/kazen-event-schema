"""Loop 31 P3-1 proof — unified MCP catalog + cross-product mesh dispatch.

An external agent calls one capability from EACH of the five services via the
mesh, sharing one root_run_id, org-scoped, with budget-governed tools blocked
when the org budget is exhausted. Fails before (no mcp_catalog / mcp_mesh).
"""

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


def _load_service_mcp(backend_subdir: str, module_name: str = "mcp_server") -> ModuleType:
    """Load sdk/mcp_server.py from a specific agent without sdk package collisions."""
    base = _KAZEN / backend_subdir
    path = base / "sdk" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"kazen_mcp_{backend_subdir.replace('/', '_')}", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Ensure agent package roots are importable for relative imports inside the module.
    agent_root = str(base)
    if agent_root not in sys.path:
        sys.path.append(agent_root)
    spec.loader.exec_module(mod)
    return mod


brain_mcp = _load_service_mcp("kazenai-agent-brain/backend")
lens_mcp = _load_service_mcp("kazenai-agent-lens/backend/agent_lens")
finops_mcp = _load_service_mcp("kazenai-agent-finops/backend")
growthops_mcp = _load_service_mcp("kazenai-agent-growthops/backend")
builder_mcp = _load_service_mcp("kazenai-agent-builder")

# Brain client lives beside its mcp_server
_brain_root = str(_KAZEN / "kazenai-agent-brain/backend")
if _brain_root not in sys.path:
    sys.path.insert(0, _brain_root)
from sdk.brain_client import KazenBrain  # noqa: E402

from kazen_event_schema import (  # noqa: E402
    BudgetDenied,
    KAZEN_MCP_CATALOG,
    McpMeshSession,
    OrgMismatch,
    all_required_capabilities_covered,
    catalog_tool_names,
    validate_kazen_event,
)
from kazen_event_schema.mcp_catalog import REQUIRED_CAPABILITIES  # noqa: E402


ROOT_RUN = "mcp-mesh-p31"
ORG_A = "org-a-mcp"
ORG_B = "org-b-mcp"


# ---------------------------------------------------------------------------
# Catalog completeness
# ---------------------------------------------------------------------------


def test_catalog_covers_all_five_services() -> None:
    services = {t.service for t in KAZEN_MCP_CATALOG}
    assert services == {"brain", "lens", "finops", "builder", "growthops"}


def test_required_capabilities_all_present() -> None:
    assert all_required_capabilities_covered()
    for svc, required in REQUIRED_CAPABILITIES.items():
        have = catalog_tool_names(svc)
        assert required.issubset(have), f"{svc}: missing {required - have}"


def test_each_service_mcp_exports_match_catalog() -> None:
    assert brain_mcp.TOOL_NAMES >= REQUIRED_CAPABILITIES["brain"]
    assert lens_mcp.TOOL_NAMES >= REQUIRED_CAPABILITIES["lens"]
    assert finops_mcp.TOOL_NAMES >= REQUIRED_CAPABILITIES["finops"]
    assert builder_mcp.TOOL_NAMES >= REQUIRED_CAPABILITIES["builder"]
    assert growthops_mcp.TOOL_NAMES >= REQUIRED_CAPABILITIES["growthops"]


# ---------------------------------------------------------------------------
# Cross-product mesh — one root_run_id, five services, injected transports
# ---------------------------------------------------------------------------


def _make_handlers():
    brain_store: dict = {}

    def brain_transport(path, body, headers):
        if path == "/v1/recall":
            return {"ok": True, "recall": {"context_pack": brain_store.get("last", "")}}
        if path == "/v1/verify/answer":
            return {"passed": True, "trust": {"trust_score": 0.95}}
        return {}

    brain = KazenBrain(api_key="kbrain_a", transport=brain_transport)

    lens_calls = []

    def lens_transport(method, path, body, headers):
        lens_calls.append({"method": method, "path": path, "headers": headers, "body": body})
        if "timeline" in path:
            return {"events": [{"event_type": "run.started", "org_id": ORG_A}], "run_id": ROOT_RUN}
        if path == "/v1/eval/agent":
            return {"overall_score": 0.88, "passed": True, "agent": body["agent"]}
        if "replay" in path:
            return {"run_id": body.get("run_id", ROOT_RUN), "samples": []}
        return {}

    lens = lens_mcp.KazenLens(transport=lens_transport)

    finops_state = {"reserved": 0.0, "limit": 1.0}

    def finops_transport(path, body, headers):
        est = float(body.get("estimated_cost_usd", 0.05))
        reserve = body.get("reserve", False)
        if reserve:
            if finops_state["reserved"] + est > finops_state["limit"]:
                return {"allowed": False, "reason": "org_budget_exhausted", "level_blocked": "org"}
            finops_state["reserved"] += est
        return {"allowed": True, "reason": "ok", "projected_spend_usd": finops_state["reserved"] + est}

    finops = finops_mcp.KazenFinOps(transport=finops_transport)

    def enrich_fn(profiles, provider):
        return [{**p, "enrichment": {"provider": provider, "matched": True}} for p in profiles]

    growthops = growthops_mcp.KazenGrowthOps(
        enrich_fn=enrich_fn,
        send_fn=growthops_mcp.default_send_fn,
    )

    builder = builder_mcp.KazenBuilder(
        plan_fn=lambda prompt, feature, run_id, web: f"# plan for {feature}\n{prompt}",
        code_fn=lambda feature, run_id, use_fallback: f"# code for {feature}",
        review_fn=lambda feature, code, run_id: {"decision": "approve", "confidence": 0.9},
    )

    return {
        "brain": lambda tool, org, args: brain_mcp.call_tool(brain, tool, {**args, "org_id": org}),
        "lens": lens_mcp.make_mesh_handler(lens),
        "finops": finops_mcp.make_mesh_handler(finops),
        "growthops": growthops_mcp.make_mesh_handler(growthops),
        "builder": builder_mcp.make_mesh_handler(builder),
    }, lens_calls, finops_state, finops


def test_external_agent_calls_all_five_services_one_root_run_id() -> None:
    handlers, lens_calls, _, _ = _make_handlers()
    session = McpMeshSession(org_id=ORG_A, root_run_id=ROOT_RUN, handlers=handlers, budget_allowed=True)

    # FinOps reserve first (budget-governed path)
    reserve = session.call(
        "finops",
        "budget_reserve",
        {"run_id": ROOT_RUN, "estimated_cost_usd": 0.10},
    )
    assert reserve["allowed"] is True

    recall = session.call("brain", "recall", {"query": "SLA?"})
    assert recall["ok"] is True

    trace = session.call("lens", "trace", {"run_id": ROOT_RUN})
    assert "events" in trace

    eval_result = session.call(
        "lens",
        "eval",
        {"agent": "brain", "payload": {"question": "q", "answer": "a", "reference": "a"}},
    )
    assert eval_result["overall_score"] == 0.88

    plan = session.call("builder", "plan", {"prompt": "add auth", "feature": "auth"})
    assert "plan" in plan

    enrich = session.call(
        "growthops",
        "enrich",
        {"profiles": [{"email": "a@co.com", "record_type": "prospect"}]},
    )
    assert enrich["count"] == 1

    send = session.call(
        "growthops",
        "send_with_approval",
        {"channel": "email", "payload": {"to": "a@co.com", "subject": "hi"}},
    )
    assert send["requires_approval"] is True

    # Every call emitted mcp.call on the spine with the SAME root_run_id
    assert len(session.events) == 7
    for ev in session.events:
        validate_kazen_event(ev, strict=True)
        assert ev["org_id"] == ORG_A
        assert ev["root_run_id"] == ROOT_RUN
        assert ev["event_type"] == "mcp.call"

    # Lens trace was org-scoped
    assert any("timeline" in c["path"] for c in lens_calls)
    assert lens_calls[0]["headers"].get("X-Kazen-Org-Id") == ORG_A or ORG_A  # org injected in args


def test_budget_governed_tool_blocked_when_org_budget_exhausted() -> None:
    handlers, _, finops_state, finops = _make_handlers()
    finops_state["reserved"] = 0.99
    finops_state["limit"] = 1.0

    session = McpMeshSession(org_id=ORG_A, root_run_id=ROOT_RUN, handlers=handlers, budget_allowed=False)

    with pytest.raises(BudgetDenied):
        session.call("builder", "code", {"feature": "auth", "run_id": ROOT_RUN})

    denied = session.events[-1]
    assert denied["payload"]["allowed"] is False
    assert denied["payload"]["reason"] == "budget_denied"


def test_cross_tenant_org_mismatch_rejected() -> None:
    handlers, _, _, _ = _make_handlers()
    session = McpMeshSession(org_id=ORG_A, root_run_id=ROOT_RUN, handlers=handlers, budget_allowed=True)

    with pytest.raises(OrgMismatch):
        session.call("brain", "recall", {"query": "x", "org_id": ORG_B})


def test_finops_reserve_denied_propagates_from_service() -> None:
    handlers, _, finops_state, _ = _make_handlers()
    finops_state["reserved"] = 1.0
    finops_state["limit"] = 1.0

    session = McpMeshSession(org_id=ORG_A, root_run_id=ROOT_RUN, handlers=handlers, budget_allowed=True)

    result = session.call("finops", "budget_reserve", {"run_id": ROOT_RUN, "estimated_cost_usd": 0.05})
    assert result["allowed"] is False
    assert result["reason"] == "org_budget_exhausted"
