"""Loop 31 P3-1 — MCP mesh dispatch: org-scoped, budget-governed, lineage-traced.

External agents call capabilities through this layer so every cross-agent MCP
invocation is traced (mcp.call KazenEvent), budget-checked, and tenant-isolated.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any, Callable, Dict, Optional

from kazen_event_schema.mcp_catalog import (
    KazenService,
    McpMeshCallRecord,
    is_budget_governed,
    lookup_tool,
)

MeshHandler = Callable[[str, str, Dict[str, Any]], Dict[str, Any]]


class BudgetDenied(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class OrgMismatch(Exception):
    pass


def _args_hash(arguments: Dict[str, Any]) -> str:
    blob = json.dumps(arguments, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def build_mcp_call_event(
    *,
    org_id: str,
    root_run_id: str,
    service: KazenService,
    tool_name: str,
    arguments: Dict[str, Any],
    allowed: bool,
    reason: str = "",
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Canonical mcp.call KazenEvent for lineage (P1-1 join key = root_run_id)."""
    return {
        "event_id": str(uuid.uuid4()),
        "org_id": org_id,
        "run_id": run_id or root_run_id,
        "root_run_id": root_run_id,
        "ts_ms": int(time.time() * 1000),
        "event_type": "mcp.call",
        "surface": f"kazenai-agent-{service}",
        "agent_id": "mcp_mesh",
        "client_id": "mcp",
        "payload": {
            "tool_name": f"{service}.{tool_name}",
            "args_hash": _args_hash(arguments),
            "allowed": allowed,
            "reason": reason or None,
        },
    }


class McpMeshSession:
    """One org-scoped MCP session sharing a root_run_id across service calls."""

    def __init__(
        self,
        *,
        org_id: str,
        root_run_id: str,
        handlers: Dict[KazenService, MeshHandler],
        budget_allowed: bool = True,
        budget_checker: Optional[Callable[[str, str, Dict[str, Any]], bool]] = None,
    ) -> None:
        self.org_id = org_id
        self.root_run_id = root_run_id
        self._handlers = handlers
        self._budget_allowed = budget_allowed
        self._budget_checker = budget_checker
        self.call_log: list[McpMeshCallRecord] = []
        self.events: list[Dict[str, Any]] = []

    def _assert_org(self, arguments: Dict[str, Any]) -> None:
        arg_org = arguments.get("org_id")
        if arg_org is not None and arg_org != self.org_id:
            raise OrgMismatch(f"org_id mismatch: session={self.org_id!r} arg={arg_org!r}")

    def _budget_ok(self, service: KazenService, tool_name: str, arguments: Dict[str, Any]) -> bool:
        if not is_budget_governed(service, tool_name):
            return True
        if self._budget_checker is not None:
            return self._budget_checker(self.org_id, self.root_run_id, arguments)
        return self._budget_allowed

    def call(self, service: KazenService, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        spec = lookup_tool(service, tool_name)
        if spec is None:
            raise ValueError(f"unknown catalog tool: {service}.{tool_name}")

        self._assert_org(arguments)
        arguments = {**arguments, "org_id": self.org_id, "root_run_id": self.root_run_id}

        if not self._budget_ok(service, tool_name, arguments):
            event = build_mcp_call_event(
                org_id=self.org_id,
                root_run_id=self.root_run_id,
                service=service,
                tool_name=tool_name,
                arguments=arguments,
                allowed=False,
                reason="budget_denied",
                run_id=arguments.get("run_id"),
            )
            self.events.append(event)
            record = McpMeshCallRecord(
                org_id=self.org_id,
                root_run_id=self.root_run_id,
                service=service,
                tool_name=tool_name,
                allowed=False,
                reason="budget_denied",
                events=[event],
            )
            self.call_log.append(record)
            raise BudgetDenied("budget_denied")

        handler = self._handlers.get(service)
        if handler is None:
            raise ValueError(f"no handler registered for service {service!r}")

        result = handler(tool_name, self.org_id, arguments)
        event = build_mcp_call_event(
            org_id=self.org_id,
            root_run_id=self.root_run_id,
            service=service,
            tool_name=tool_name,
            arguments=arguments,
            allowed=True,
            run_id=arguments.get("run_id"),
        )
        self.events.append(event)
        record = McpMeshCallRecord(
            org_id=self.org_id,
            root_run_id=self.root_run_id,
            service=service,
            tool_name=tool_name,
            allowed=True,
            events=[event],
        )
        self.call_log.append(record)
        return result


def build_inter_agent_call_event(
    *,
    org_id: str,
    root_run_id: str,
    caller: KazenService,
    callee: KazenService,
    tool_name: str,
    arguments: Dict[str, Any],
    allowed: bool,
    reason: str = "",
    run_id: Optional[str] = None,
    budget_reserved_usd: Optional[float] = None,
) -> Dict[str, Any]:
    """Canonical mcp.call for agent→agent hops (caller recorded for lineage joins)."""
    event = build_mcp_call_event(
        org_id=org_id,
        root_run_id=root_run_id,
        service=callee,
        tool_name=tool_name,
        arguments=arguments,
        allowed=allowed,
        reason=reason,
        run_id=run_id,
    )
    payload = dict(event.get("payload") or {})
    payload["caller_service"] = caller
    payload["callee_service"] = callee
    payload["inter_agent"] = True
    if budget_reserved_usd is not None:
        payload["budget_reserved_usd"] = budget_reserved_usd
    event["payload"] = payload
    event["surface"] = f"kazenai-agent-{caller}"
    event["agent_id"] = f"{caller}_mesh"
    return event


class InterAgentMesh:
    """Route cross-agent calls through the MCP mesh (traced + budgeted + org-scoped).

    Every hop reserves against FinOps first, then dispatches to the callee service.
    Emits inter-agent ``mcp.call`` events on the shared ``root_run_id`` (P1-1 lineage).
    """

    def __init__(
        self,
        *,
        caller: KazenService,
        org_id: str,
        root_run_id: str,
        session: McpMeshSession,
        reserve_usd: float = 0.01,
        event_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.caller = caller
        self.org_id = org_id
        self.root_run_id = root_run_id
        self._session = session
        self._reserve_usd = reserve_usd
        self._event_sink = event_sink
        self.events: list[Dict[str, Any]] = []

    @property
    def lineage_events(self) -> list[Dict[str, Any]]:
        """All mesh-emitted events (FinOps reserve + callee + inter-agent audit)."""
        return list(self._session.events) + list(self.events)

    def _sink(self, event: Dict[str, Any]) -> None:
        self.events.append(event)
        if self._event_sink is not None:
            self._event_sink(event)

    def _reserve_budget(self, run_id: str) -> Dict[str, Any]:
        return self._session.call(
            "finops",
            "budget_reserve",
            {
                "org_id": self.org_id,
                "run_id": run_id or self.root_run_id,
                "estimated_cost_usd": self._reserve_usd,
            },
        )

    def invoke(
        self,
        callee: KazenService,
        tool_name: str,
        arguments: Dict[str, Any],
        *,
        run_id: Optional[str] = None,
        skip_budget: bool = False,
    ) -> Dict[str, Any]:
        rid = run_id or arguments.get("run_id") or self.root_run_id
        if arguments.get("org_id") is not None and arguments.get("org_id") != self.org_id:
            from kazen_event_schema.mcp_mesh import OrgMismatch

            raise OrgMismatch(
                f"org_id mismatch: mesh={self.org_id!r} arg={arguments.get('org_id')!r}"
            )
        arguments = {**arguments, "org_id": self.org_id, "root_run_id": self.root_run_id, "run_id": rid}

        reserved_usd: Optional[float] = None
        if not skip_budget:
            reserve = self._reserve_budget(rid)
            if not reserve.get("allowed", False):
                event = build_inter_agent_call_event(
                    org_id=self.org_id,
                    root_run_id=self.root_run_id,
                    caller=self.caller,
                    callee=callee,
                    tool_name=tool_name,
                    arguments=arguments,
                    allowed=False,
                    reason=str(reserve.get("reason") or "budget_denied"),
                    run_id=rid,
                )
                self._sink(event)
                raise BudgetDenied(str(reserve.get("reason") or "budget_denied"))
            reserved_usd = self._reserve_usd

        try:
            result = self._session.call(callee, tool_name, arguments)
        except (BudgetDenied, OrgMismatch):
            raise
        except Exception as exc:
            event = build_inter_agent_call_event(
                org_id=self.org_id,
                root_run_id=self.root_run_id,
                caller=self.caller,
                callee=callee,
                tool_name=tool_name,
                arguments=arguments,
                allowed=False,
                reason=str(exc),
                run_id=rid,
                budget_reserved_usd=reserved_usd,
            )
            self._sink(event)
            raise

        event = build_inter_agent_call_event(
            org_id=self.org_id,
            root_run_id=self.root_run_id,
            caller=self.caller,
            callee=callee,
            tool_name=tool_name,
            arguments=arguments,
            allowed=True,
            run_id=rid,
            budget_reserved_usd=reserved_usd,
        )
        self._sink(event)
        return result
