# Releasing kazen-event-schema

`kazen-event-schema` is the contract every KazenAI SDK and service relies on, so
releases are additive by default. Never remove an event type or rename a field
without a deprecation window.

## Versioning

- **Patch** (`0.6.4 → 0.6.5`): additive only — a new event type or a new
  optional field — or documentation. Safe for every consumer.
- **Minor** (`0.6.x → 0.7.0`): may add required fields with sensible defaults.
  Consumers update their pinned range.
- **Major** (`0.x → 1.0`): may remove or rename, after one full minor release of
  deprecation.

## Steps

1. Set the same version in `pyproject.toml` and `kazen_event_schema/__init__.py`,
   and add a section at the top of `CHANGELOG.md` headed `## X.Y.Z - YYYY-MM-DD` (the release date).
2. Register every new event type in `KNOWN_EVENT_TYPES`.
3. Run the tests: `pip install -e ".[dev]" && pytest`.
4. Run the `kazenai` test suite against the new version
   (`pip install -e ../kazen-event-schema` in a `kazenai-core` checkout, then
   `pytest`). A failure there means the change is breaking.
5. Commit, push, and wait for CI.
6. Tag, publish and create the GitHub Release:

   ```bash
   git tag -a vX.Y.Z -m "kazen-event-schema X.Y.Z"
   git push origin vX.Y.Z
   # The Release body is this version's CHANGELOG.md section plus a docs and support line.
   awk '/^## /{p=0} /^## X.Y.Z /{p=1; next} p' CHANGELOG.md > /tmp/notes-X.Y.Z.md
   printf '\nDocs: https://docs.kazenai.com/ · Support: open an issue at https://github.com/kazenai-ai/kazen-event-schema/issues\n' >> /tmp/notes-X.Y.Z.md
   gh release create vX.Y.Z --title "kazen-event-schema X.Y.Z" --notes-file /tmp/notes-X.Y.Z.md --verify-tag
   ```

7. Raise the lower bound in `kazenai` only when it needs something new from this
   release.
