# kazen-event-schema

[![PyPI](https://img.shields.io/pypi/v/kazen-event-schema.svg)](https://pypi.org/project/kazen-event-schema/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://github.com/kazenai-ai/kazen-event-schema/blob/main/LICENSE)

**The shared event contract for KazenAI.** One schema so Agent FinOps, its run receipts, and the SDKs speak the same language about cost, runs, and control decisions.

**Install:** [PyPI · kazen-event-schema](https://pypi.org/project/kazen-event-schema/) · **Docs:** [Event reference](https://docs.kazenai.com/reference/events/) · **Products:** [kazenai.com](https://kazenai.com)

**Source:** [github.com/kazenai-ai/kazen-event-schema](https://github.com/kazenai-ai/kazen-event-schema)

---

## Why it exists

Hard spending limits only work if every part of the stack agrees on what an “event” is:

- SDKs emit what happened (model calls, denials, settlements)
- FinOps accounts for spend and policy decisions
- Run receipts explain each run and decision with the same identifiers

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
| Human gates | `gate.decision`, `human_gate` |
| FinOps / control | `finops.budget.reserve`, `finops.budget.denied`, `finops.trajectory`, `finops.loop.anomaly`, `finops.circuit_breaker.opened`, `finops.pause`, `finops.resumed` |
| Run lifecycle | `run.started`, `run.finished`, `run.failed` |

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
| `tokens` / `tokens_used` / `cost_usd` | optional | Usage and spend; token aliases normalize to the same count and conflicting values are rejected |
| `payload` | optional | Model id, tool names, refs |

---

## Used by

| Package / service | Role |
|-------------------|------|
| [`kazenai`](https://pypi.org/project/kazenai/) / [`kazenai-finops`](https://pypi.org/project/kazenai-finops/) | SDK emit path |
| Agent FinOps | Accounting + ingest |
| Agent FinOps run receipts | Run timelines + decision evidence |

## Consuming events safely

If you ingest `KazenEvent`s in your own service:

- Validate each event with `KazenEvent` before reading fields; unknown top-level
  fields are rejected.
- Treat `tokens` and `tokens_used` (and the timestamp aliases) as the same
  value — the model normalizes them and rejects conflicting values.
- Use `event_id` for idempotent ingest: a repeated event with the same content
  is a duplicate, a repeated id with different content is a conflict.
- Pin a compatible range (`kazen-event-schema>=0.6,<0.7`) and run your
  ingest-to-storage tests when you upgrade.

---

## License

Apache License 2.0. See [LICENSE](https://github.com/kazenai-ai/kazen-event-schema/blob/main/LICENSE) and [NOTICE](https://github.com/kazenai-ai/kazen-event-schema/blob/main/NOTICE).

Products: [kazenai.com](https://kazenai.com) · **founder@kazenai.com**
