# Changelog

Notable changes to `kazen-event-schema`, newest first. Each release is also published on
[GitHub Releases](https://github.com/kazenai-ai/kazen-event-schema/releases).

## 0.6.6 - 2026-10-28

Removes event types and helpers left over from earlier KazenAI products. No
current KazenAI component sends or reads them, and the events the SDKs and
Agent FinOps use are unchanged. `kazenai` 1.2.0 requires this version.

### Before you upgrade

If your code imports any of the modules below, stay on 0.6.5.

### Removed

- Modules: `kazen_event_schema.company_loop`, `.orchestration`, `.mcp_catalog`,
  `.mcp_mesh` and `.memory_write`, with everything they exported.
- Payload classes: `FinOpsOptimizationPayload`, the three `GrowthOps*` payloads,
  `MemoryForgottenPayload` and `MemoryRecallBenchmarkPayload`.
- 81 unused event types from `KNOWN_EVENT_TYPES` (for example `sales.*`,
  `goals.*`, `orchestration.*` and `worktree.*`). Events with these types still
  validate unless you pass `strict=True`.
- `PolicyAction` kinds other than `"spend"`, and the matching `OrgPolicy`
  settings; organization policy now covers spend only.
- `GateDecisionPayload.brain_trace_node_id`. Payloads still accept extra fields.

### Changed

- `KazenEvent` defaults: `surface` is `"unspecified"` and `agent_id` is
  `"default"` when an emitter does not set them.

```bash
python -m pip install kazen-event-schema==0.6.6
```

## 0.6.5 - 2026-10-12

Documentation and packaging release. No change to the event model or any event
type; upgrading from 0.6.4 is safe.

- Rewritten README guidance for services that consume `KazenEvent`s.
- Plain-language docstrings and comments.
- The source distribution ships the package, licence and README only.

Earlier releases: [GitHub Releases](https://github.com/kazenai-ai/kazen-event-schema/releases).
