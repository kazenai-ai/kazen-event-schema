# kazen-event-schema — Deploy

Canonical `KazenEvent` Python package shared across orchestrator, FinOps, Lens, and `kazenai-core`.

## Prerequisites

- Python 3.10+
- PyPI credentials for release (maintainers only)

## Build / test

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest   # enforces ≥80% coverage on kazen_event_schema
python -m build
```

## Docker

Library only — no runtime container. Install in service images:

```dockerfile
COPY kazen-event-schema /tmp/kazen-event-schema
RUN pip install /tmp/kazen-event-schema
```

Or pin from PyPI: `pip install kazen-event-schema==0.6.0`

## Required environment

None at package level. Downstream services set ingest URLs and tenant IDs when emitting events.

## Health / verification

No HTTP endpoint. Verify install:

```bash
python -c "from kazen_event_schema import KazenEvent; print(KazenEvent.__name__)"
pytest tests/ -q
```

Release process: [RELEASING.md](RELEASING.md).
