"""Event types named in the README must exist in the registry."""

import re
from pathlib import Path

from kazen_event_schema import KNOWN_EVENT_TYPES, normalize_event_type

README = Path(__file__).resolve().parents[1] / "README.md"


def test_readme_common_event_types_are_registered():
    text = README.read_text(encoding="utf-8")
    section = text.split("## Common event types", 1)[1].split("\n---", 1)[0]
    names = re.findall(r"`([a-z0-9_.]+)`", section)
    assert "model.call" in names
    missing = [n for n in names if normalize_event_type(n) not in KNOWN_EVENT_TYPES]
    assert not missing, f"README names unregistered event types: {missing}"
