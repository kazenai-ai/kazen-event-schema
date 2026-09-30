# kazen-event-schema

[![PyPI](https://img.shields.io/pypi/v/kazen-event-schema.svg)](https://pypi.org/project/kazen-event-schema/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

**The shared event contract for KazenAI.** One schema so Agent FinOps, Agent Lens, and the SDKs speak the same language about cost, runs, and control decisions.

**Install:** [PyPI · kazen-event-schema](https://pypi.org/project/kazen-event-schema/) · **Products:** [kazenai.com](https://kazenai.com)

---

## Why it exists

Economic control only works if every surface agrees on what an “event” is:

- SDKs emit what happened (model calls, denials, settlements)
- FinOps accounts for spend and policy decisions
- Lens investigates failures with the same identifiers

`kazen-event-schema` is that contract — a small, versioned Pydantic model used across the stack.

---

## Install

```bash
python -m pip install kazen-event-schema
```

Requires Python 3.10+. Pulled in automatically when you install [`kazenai`](https://pypi.org/project/kazenai/) or [`kazenai-finops`](https://pypi.org/project/kazenai-finops/).

---

## Quick start

```python
from kazen_event_schema import KazenEvent, normalize_event_type, is_model_call

assert normalize_event_type("llm.call") == "model.call"
assert is_model_call("model.call")

event = KazenEvent(
    schema_version="1.2",
    event_id="evt_…",
    ts_ms=1_700_000_000_000,
    event_type="model.call",
    org_id="org-a",
    workspace_id="prod",
    project_id="prod",
    surface="sdk",
    agent_id="support-agent",
    agent_role="agent",
    run_id="run-1",
    cost_usd=0.0042,
)
```

---

## Common event types

| Area | Examples |
|------|----------|
| Model invocation | `model.call` (legacy `llm.call` normalizes at ingest) |
| Human gates | `gate.decision`, `human_gate`, `human.gate` |
| FinOps / control | `finops.trajectory`, `finops.circuit_breaker.opened`, `finops.pause`, `finops.resumed` |
| Run lifecycle | `run.started`, `run.completed`, `run.failed` |

---

## Core fields

| Field | Required | Purpose |
|-------|----------|---------|
| `schema_version` | yes | `1.0`, `1.1`, or `1.2` |
| `event_id` | yes | Stable id for idempotent ingest |
| `ts_ms` | yes | Unix milliseconds |
| `event_type` | yes | Dotted lowercase type |
| `org_id` | yes | Tenant |
| `workspace_id` / `project_id` | yes | Workspace scope |
| `run_id` | recommended | Correlates steps in a run |
| `step_id` / `parent_step_id` | recommended / optional | Step tree for multi-agent runs |
| `tokens` / `cost_usd` | optional | Usage and spend |
| `payload` | optional | Model id, tool names, refs |

---

## Used by

| Package / service | Role |
|-------------------|------|
| [`kazenai`](https://pypi.org/project/kazenai/) / [`kazenai-finops`](https://pypi.org/project/kazenai-finops/) | SDK emit path |
| Agent FinOps | Accounting + ingest |
| Agent Lens | Investigation + timelines |

---

## License

Apache License 2.0. See LICENSE and NOTICE.

Products: [kazenai.com](https://kazenai.com) · **founder@kazenai.com**
