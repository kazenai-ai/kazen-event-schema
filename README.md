# kazen-event-schema

[![Local package](https://img.shields.io/badge/package-local%20v0.6.0-blue.svg)](../WORKSPACE.md)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![LLM calls guarded](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/kazenai-ai/kazenai-finops-sdk/main/badge/llm-guard.json)](https://github.com/kazenai-ai/kazenai-finops-sdk/blob/main/scripts/audit_llm_calls_all.py)

Canonical `KazenEvent` schema shared across KazenAI services (orchestrator, FinOps, AgentLens, `kazenai-core`).

**Quickstart:** [kazenai.com/onboarding](https://kazenai.com/onboarding)

```bash
pip install -e ./kazen-event-schema
```

Publishing status: this workspace version is not yet published on PyPI. Use the
local editable install above until the package release workflow is moved into a
real repo and run.

## Canonical event types

- **Model invocation:** use `model.call` (not `llm.call`; legacy `llm.call` is normalized at ingest).
- **Human gates:** `gate.decision`, `human_gate`, `human.gate`
- **FinOps:** `finops.trajectory`, `finops.circuit_breaker.opened`, `finops.pause`, `finops.resumed`
- **Run lifecycle:** `run.started`, `run.completed`, `run.failed`

```python
from kazen_event_schema import KazenEvent, normalize_event_type, is_model_call

assert normalize_event_type("llm.call") == "model.call"
assert is_model_call("model.call")
```

## Required / recommended fields (v1.2)

| Field | Required | Purpose |
|-------|----------|---------|
| `schema_version` | yes | `1.0`, `1.1`, or `1.2` |
| `event_id` | yes | UUID; idempotent ingest |
| `ts_ms` | yes | Unix ms timestamp |
| `event_type` | yes | Dotted lowercase (e.g. `model.call`) |
| `org_id` | yes | Tenant |
| `workspace_id` / `project_id` | yes | Workspace scope (alias: `project_id` → workspace) |
| `run_id` | recommended | Correlates all steps in a run |
| `step_id` | recommended | Step within run |
| `parent_step_id` | optional | Multi-agent tree |
| `agent_role` | recommended | planner, coder, brain, etc. |
| `tokens` / `tokens_used` | optional | Token count (synced if one set) |
| `cost_usd` | optional | Step cost |
| `gate_decision` | optional | proceed, rejected, retry_plan, … |
| `gate_latency_s` | optional | Human gate wait time |
| `payload` | optional | Tool names, model id, I/O refs |

## Service ports

See [../PORTS.md](../PORTS.md).
