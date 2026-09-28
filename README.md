# kazen-event-schema

[![PyPI](https://img.shields.io/pypi/v/kazen-event-schema.svg)](https://pypi.org/project/kazen-event-schema/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

Canonical `KazenEvent` schema shared across KazenAI services (orchestrator, FinOps, AgentLens, `kazenai`).

**Install:** [PyPI · kazen-event-schema](https://pypi.org/project/kazen-event-schema/) · **Products:** [kazenai.com](https://kazenai.com)

```bash
python -m pip install kazen-event-schema
```

**Published on PyPI** as `kazen-event-schema` **0.6.2**. Editable `pip install -e ./kazen-event-schema` remains available for workspace contributors.

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

See [../PORTS.md](../PORTS.md) when working from a full KazenAI workspace checkout.

## License

Apache License 2.0. See LICENSE and NOTICE.
