"""Package metadata and version-authority tests for kazen-event-schema."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_EXPECTED_RELEASE = "0.6.3"
_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _pyproject_version() -> str:
    text = _PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    assert match is not None, "pyproject.toml must declare version"
    return match.group(1)


def _pyproject_urls() -> dict[str, str]:
    text = _PYPROJECT.read_text(encoding="utf-8")
    block = re.search(r"(?ms)^\[project\.urls\]\n(.*?)(?:\n\[|\Z)", text)
    assert block is not None, "pyproject.toml must declare [project.urls]"
    urls: dict[str, str] = {}
    for line in block.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        urls[key.strip().strip('"')] = value.strip().strip('"')
    return urls


def test_version_authority_matches_pyproject():
    import kazen_event_schema as kes

    py_version = _pyproject_version()
    assert py_version == _EXPECTED_RELEASE
    assert kes.__version__ == py_version


def test_installed_distribution_version_when_available():
    import kazen_event_schema as kes
    from importlib.metadata import PackageNotFoundError, version

    try:
        dist_version = version("kazen-event-schema")
    except PackageNotFoundError:
        pytest.skip("kazen-event-schema distribution metadata not installed")
    assert dist_version == _EXPECTED_RELEASE
    assert kes.__version__ == dist_version


def test_project_urls_point_at_canonical_public_surfaces():
    urls = _pyproject_urls()
    assert urls["Homepage"] == "https://kazenai.com"
    assert urls["Documentation"] == "https://docs.kazenai.com/reference/events/"
    assert urls["Repository"] == "https://github.com/kazenai-ai/kazen-event-schema"
    assert urls["Changelog"] == "https://github.com/kazenai-ai/kazen-event-schema/releases"
    assert urls["Bug Tracker"] == "https://github.com/kazenai-ai/kazen-event-schema/issues"
    assert "github.com/KazenAI/" not in " ".join(urls.values())
    assert "github.com/kazenai/" not in " ".join(urls.values())
