"""Loop 31 P3-1 — unified MCP catalog across all five KazenAI agents.

The platform becomes an OS: every capability is callable via MCP, org-scoped,
and budget-governed where spend is involved. This module is the single catalog
on the KazenEvent spine — no parallel tool registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Literal, Optional

KazenService = Literal["brain", "lens", "finops", "builder", "growthops"]

# Capabilities the mesh must expose (one tool per clause minimum).
REQUIRED_CAPABILITIES: Dict[KazenService, FrozenSet[str]] = {
    "brain": frozenset({"recall", "verify"}),
    "lens": frozenset({"trace", "eval", "replay"}),
    "finops": frozenset({"budget_check", "budget_reserve"}),
    "builder": frozenset({"plan", "review_code", "code"}),
    "growthops": frozenset({"enrich", "send_with_approval"}),
}


@dataclass(frozen=True)
class McpToolSpec:
    """One MCP tool entry in the unified catalog."""

    service: KazenService
    name: str
    description: str
    input_schema: Dict[str, Any]
    org_scoped: bool = True
    budget_governed: bool = False
    requires_approval: bool = False

    def to_mcp_dict(self) -> Dict[str, Any]:
        return {
            "name": f"{self.service}.{self.name}",
            "description": self.description,
            "inputSchema": self.input_schema,
            "org_scoped": self.org_scoped,
            "budget_governed": self.budget_governed,
            "requires_approval": self.requires_approval,
        }


def _brain_tools() -> List[McpToolSpec]:
    common_org = {"org_id": {"type": "string", "description": "Tenant org (resolved from API key when omitted)."}}
    return [
        McpToolSpec(
            service="brain",
            name="recall",
            description="Retrieve memory relevant to a query (scoped to your org).",
            input_schema={
                "type": "object",
                "properties": {**common_org, "query": {"type": "string"}, "top_k": {"type": "integer", "default": 8}},
                "required": ["query"],
            },
        ),
        McpToolSpec(
            service="brain",
            name="verify",
            description="Check whether an answer is supported by memory; returns a trust score.",
            input_schema={
                "type": "object",
                "properties": {**common_org, "answer": {"type": "string"}, "query": {"type": "string", "default": ""}},
                "required": ["answer"],
            },
        ),
        McpToolSpec(
            service="brain",
            name="remember",
            description="Store a fact in KazenAI Brain memory. Returns the created node_id.",
            input_schema={
                "type": "object",
                "properties": {
                    **common_org,
                    "content": {"type": "string"},
                    "source_type": {"type": "string", "default": "idea_raw"},
                    "title": {"type": "string", "default": ""},
                },
                "required": ["content"],
            },
        ),
    ]


def _lens_tools() -> List[McpToolSpec]:
    run_fields = {
        "org_id": {"type": "string"},
        "run_id": {"type": "string"},
        "root_run_id": {"type": "string"},
    }
    return [
        McpToolSpec(
            service="lens",
            name="trace",
            description="Fetch the event timeline for a run (trace view).",
            input_schema={
                "type": "object",
                "properties": {**run_fields, "limit": {"type": "integer", "default": 500}},
                "required": ["run_id"],
            },
        ),
        McpToolSpec(
            service="lens",
            name="eval",
            description="Score an agent output via the shared Lens eval substrate.",
            input_schema={
                "type": "object",
                "properties": {
                    **run_fields,
                    "agent": {"type": "string", "enum": ["brain", "builder", "growthops", "finops"]},
                    "payload": {"type": "object"},
                },
                "required": ["agent", "payload"],
            },
        ),
        McpToolSpec(
            service="lens",
            name="replay",
            description="Replay a run from a step (offline trajectory re-execution).",
            input_schema={
                "type": "object",
                "properties": {
                    **run_fields,
                    "step_id": {"type": "string"},
                    "n": {"type": "integer", "default": 1},
                },
                "required": ["run_id", "step_id"],
            },
            budget_governed=True,
        ),
    ]


def _finops_tools() -> List[McpToolSpec]:
    budget_body = {
        "org_id": {"type": "string"},
        "workspace_id": {"type": "string", "default": "default"},
        "run_id": {"type": "string"},
        "estimated_cost_usd": {"type": "number", "default": 0.05},
        "feature": {"type": "string"},
    }
    return [
        McpToolSpec(
            service="finops",
            name="budget_check",
            description="Pre-flight org budget check (read-only; does not reserve).",
            input_schema={
                "type": "object",
                "properties": {**budget_body, "reserve": {"type": "boolean", "default": False}},
                "required": ["org_id", "run_id"],
            },
            budget_governed=True,
        ),
        McpToolSpec(
            service="finops",
            name="budget_reserve",
            description="Reserve spend against the org budget before an agent action.",
            input_schema={
                "type": "object",
                "properties": {**budget_body, "reserve": {"type": "boolean", "default": True}},
                "required": ["org_id", "run_id"],
            },
            budget_governed=True,
        ),
    ]


def _builder_tools() -> List[McpToolSpec]:
    feature_run = {
        "feature": {"type": "string"},
        "run_id": {"type": "string"},
        "org_id": {"type": "string"},
    }
    return [
        McpToolSpec(
            service="builder",
            name="plan",
            description="Generate a structured actions.md plan for a feature.",
            input_schema={
                "type": "object",
                "properties": {**feature_run, "prompt": {"type": "string"}, "web_context": {"type": "string", "default": ""}},
                "required": ["prompt", "feature"],
            },
            budget_governed=True,
        ),
        McpToolSpec(
            service="builder",
            name="review_code",
            description="Run the Critic on generated code against the plan.",
            input_schema={
                "type": "object",
                "properties": {**feature_run, "generated_code": {"type": "string"}},
                "required": ["feature", "generated_code"],
            },
            budget_governed=True,
        ),
        McpToolSpec(
            service="builder",
            name="code",
            description="Generate implementation code from an approved plan.",
            input_schema={
                "type": "object",
                "properties": {**feature_run, "use_fallback": {"type": "boolean", "default": False}},
                "required": ["feature"],
            },
            budget_governed=True,
        ),
    ]


def _growthops_tools() -> List[McpToolSpec]:
    return [
        McpToolSpec(
            service="growthops",
            name="enrich",
            description="Enrich prospect profiles with third-party signals (outbound only).",
            input_schema={
                "type": "object",
                "properties": {
                    "org_id": {"type": "string"},
                    "run_id": {"type": "string"},
                    "profiles": {"type": "array", "items": {"type": "object"}},
                    "provider": {"type": "string", "default": "clearbit"},
                },
                "required": ["profiles"],
            },
            budget_governed=True,
        ),
        McpToolSpec(
            service="growthops",
            name="plan_multichannel",
            description="Plan email + LinkedIn + voice follow-ups from call qualification.",
            input_schema={
                "type": "object",
                "properties": {
                    "org_id": {"type": "string"},
                    "run_id": {"type": "string"},
                    "prospect_name": {"type": "string"},
                    "prospect_email": {"type": "string"},
                    "linkedin_url": {"type": "string"},
                    "company": {"type": "string"},
                    "qualification": {"type": "object"},
                    "source_channel": {"type": "string", "default": "call_transcript"},
                },
                "required": ["prospect_name", "qualification"],
            },
            requires_approval=True,
        ),
        McpToolSpec(
            service="growthops",
            name="score_inbound",
            description="Score inbound signal intent; prioritize over cold outbound when hot.",
            input_schema={
                "type": "object",
                "properties": {
                    "org_id": {"type": "string"},
                    "run_id": {"type": "string"},
                    "text": {"type": "string"},
                    "signal_type": {"type": "string", "default": "inbound_reply"},
                    "reply_classification": {"type": "string"},
                    "prospect_email": {"type": "string"},
                    "source_channel": {"type": "string"},
                    "multichannel_plan": {"type": "object"},
                },
                "required": ["text"],
            },
        ),
        McpToolSpec(
            service="growthops",
            name="learn_from_replies",
            description="Learn from reply outcomes; suggest next sequence touch with Lens lift proof.",
            input_schema={
                "type": "object",
                "properties": {
                    "org_id": {"type": "string"},
                    "run_id": {"type": "string"},
                    "outcomes": {"type": "array", "items": {"type": "object"}},
                    "prospect_name": {"type": "string"},
                    "company": {"type": "string"},
                    "touch_number": {"type": "integer", "default": 2},
                    "inbound_text": {"type": "string"},
                    "baseline_draft": {"type": "string"},
                    "sequence_id": {"type": "string"},
                },
                "required": ["outcomes", "prospect_name", "inbound_text"],
            },
        ),
        McpToolSpec(
            service="growthops",
            name="send_with_approval",
            description="Queue an external send for human approval (never executes inline).",
            input_schema={
                "type": "object",
                "properties": {
                    "org_id": {"type": "string"},
                    "run_id": {"type": "string"},
                    "channel": {"type": "string", "enum": ["email", "linkedin", "voice"]},
                    "payload": {"type": "object"},
                    "action_key": {"type": "string", "default": "outreach_send"},
                },
                "required": ["channel", "payload"],
            },
            requires_approval=True,
            budget_governed=True,
        ),
    ]


KAZEN_MCP_CATALOG: List[McpToolSpec] = (
    _brain_tools() + _lens_tools() + _finops_tools() + _builder_tools() + _growthops_tools()
)

CATALOG_BY_SERVICE: Dict[KazenService, List[McpToolSpec]] = {}
for _svc in ("brain", "lens", "finops", "builder", "growthops"):
    CATALOG_BY_SERVICE[_svc] = [t for t in KAZEN_MCP_CATALOG if t.service == _svc]


def catalog_tool_names(service: Optional[KazenService] = None) -> FrozenSet[str]:
    if service is None:
        return frozenset(t.name for t in KAZEN_MCP_CATALOG)
    return frozenset(t.name for t in CATALOG_BY_SERVICE.get(service, []))


def required_capabilities_covered() -> Dict[KazenService, bool]:
    """True when every required capability for a service has a catalog entry."""
    out: Dict[KazenService, bool] = {}
    for svc, required in REQUIRED_CAPABILITIES.items():
        have = catalog_tool_names(svc)
        out[svc] = required.issubset(have)
    return out


def all_required_capabilities_covered() -> bool:
    return all(required_capabilities_covered().values())


def lookup_tool(service: KazenService, name: str) -> Optional[McpToolSpec]:
    for spec in CATALOG_BY_SERVICE.get(service, []):
        if spec.name == name:
            return spec
    return None


def is_budget_governed(service: KazenService, name: str) -> bool:
    spec = lookup_tool(service, name)
    return bool(spec and spec.budget_governed)


@dataclass
class McpMeshCallRecord:
    """Audit record for one mesh dispatch (joins P1-1 lineage via root_run_id)."""

    org_id: str
    root_run_id: str
    service: KazenService
    tool_name: str
    allowed: bool
    reason: str = ""
    events: List[Dict[str, Any]] = field(default_factory=list)
