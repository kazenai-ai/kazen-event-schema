# Releasing kazen-event-schema

This is the canonical event schema shared by every KazenAI service. Any
breaking change here cascades into the orchestrator, finops backend, agent-lens
backend, and the pip-installable kazenai-core SDK. **Treat releases as
binding contracts** — never delete an event_type or rename a field without a
deprecation window.

---

## 0. Versioning policy

- Patch (`0.3.0 → 0.3.1`): additive only (new event_type, new optional field).
  Safe to deploy to all consumers without coordination.
- Minor (`0.3.x → 0.4.0`): may add required fields with sensible defaults.
  Coordinate with downstream consumers; bump deps in lock-step.
- Major (`0.x.y → 1.0.0`): may remove or rename. Triggers a deprecation
  window of one full minor release before the removal.

---

## 1. Pre-flight

1. Both version locations match:
   - `kazen_event_schema/__init__.py: __version__`
   - `pyproject.toml: version`
2. Every new event_type is added to `KNOWN_EVENT_TYPES` in
   `kazen_event_schema/__init__.py`.
3. Every new event_type is also mirrored in
   `kazenai-agent-builder/state/kazenai_schema.py` (orchestrator-local
   fallback registry).

---

## 2. Run tests in the schema repo

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
pytest -v
```

---

## 3. Run downstream consumer tests against the new schema

This is the **load-bearing step** — without it, the schema bump can silently
break downstream consumers.

```bash
# orchestrator
cd ../kazenai-agent-builder && pip install -e ../kazen-event-schema && \
  pytest tests/test_state/test_kazen_event_schema.py tests/test_state/test_kazen_event_emitter.py -v

# hosted finops
cd ../kazenai-agent-finops && pip install -e ../kazen-event-schema && \
  make test-clean

# standalone agent-lens
cd ../kazenai-agent-lens/backend && pip install -e ../../kazen-event-schema && \
  pytest -v

# kazenai-core SDK
cd ../kazenai-core && pip install -e ../kazen-event-schema && \
  pytest -v
```

If any fail, the schema change is breaking for that consumer. Either:
   a. roll back the schema change, or
   b. open coordinated PRs in every affected repo, or
   c. add a deprecation shim (preferred for renames).

---

## 4. Tag, push, publish

```bash
git tag -a vX.Y.Z -m "Schema vX.Y.Z — <event_types added/changed>"
git push origin main --tags

# Then bump the dependency in downstream repos:
# - kazenai-agent-builder/requirements.txt
# - kazenai-agent-finops/backend/requirements.txt
# - kazenai-agent-lens/backend/requirements.txt
# - kazenai-core/pyproject.toml
```

---

## Anti-patterns

- Adding an event_type to one registry but not the orchestrator-local mirror
- Bumping the version in `__init__.py` but not `pyproject.toml` (or vice versa)
- Releasing a minor bump without running downstream consumer tests
- Removing or renaming an event_type without a deprecation window
