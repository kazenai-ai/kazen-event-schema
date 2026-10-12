"""FINAL_1_b_final P2 — tokens/timestamp alias normalization and conflicts."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from kazen_event_schema import KazenEvent, canonicalize_event_dict


def _base(**overrides):
    raw = {
        "schema_version": "1.2",
        "ts_ms": 1_700_000_000_000,
        "event_id": "evt_p2_alias_base01",
        "org_id": "org_p2",
        "project_id": "default",
        "surface": "kazenai-sdk",
        "agent_id": "agent_p2",
        "event_type": "model.call",
    }
    raw.update(overrides)
    return raw


def test_tokens_alone_normalizes() -> None:
    ev = KazenEvent.model_validate(_base(tokens=17))
    assert ev.tokens == 17
    assert ev.tokens_used == 17


def test_tokens_used_alone_normalizes() -> None:
    ev = KazenEvent.model_validate(_base(tokens_used=0))
    assert ev.tokens == 0
    assert ev.tokens_used == 0


def test_tokens_both_equal_accepted() -> None:
    ev = KazenEvent.model_validate(_base(tokens=17, tokens_used=17))
    assert ev.tokens_used == 17


def test_tokens_conflict_rejected() -> None:
    with pytest.raises(ValidationError) as excinfo:
        KazenEvent.model_validate(_base(tokens=17, tokens_used=18))
    assert "tokens_conflict" in str(excinfo.value)


def test_tokens_missing_stays_null() -> None:
    ev = KazenEvent.model_validate(_base())
    assert ev.tokens is None
    assert ev.tokens_used is None


def test_timestamp_alias_alone() -> None:
    raw = _base()
    del raw["ts_ms"]
    raw["timestamp_ms"] = 1_700_000_000_111
    ev = KazenEvent.model_validate(raw)
    assert ev.ts_ms == 1_700_000_000_111
    assert ev.timestamp_ms == 1_700_000_000_111


def test_timestamp_both_consistent() -> None:
    ev = KazenEvent.model_validate(_base(ts_ms=5, timestamp_ms=5))
    assert ev.ts_ms == 5
    assert ev.timestamp_ms == 5


def test_timestamp_conflict_rejected() -> None:
    with pytest.raises(ValidationError) as excinfo:
        KazenEvent.model_validate(_base(ts_ms=1, timestamp_ms=2))
    assert "timestamp_conflict" in str(excinfo.value)


def test_explicit_timestamp_not_overwritten_by_default() -> None:
    ev = KazenEvent.model_validate(_base(ts_ms=42))
    assert ev.ts_ms == 42


def test_legacy_schema_versions_accepted() -> None:
    for version in ("1.0", "1.1", "1.2"):
        ev = KazenEvent.model_validate(_base(schema_version=version, tokens=17))
        assert ev.schema_version == version
        assert ev.tokens_used == 17


def test_unknown_schema_version_rejected() -> None:
    with pytest.raises(ValidationError) as excinfo:
        KazenEvent.model_validate(_base(schema_version="9.9"))
    assert "unknown_schema_version" in str(excinfo.value)


def test_invalid_money_rejected() -> None:
    with pytest.raises(ValidationError) as excinfo:
        KazenEvent.model_validate(_base(cost_usd=float("nan")))
    assert "invalid_money" in str(excinfo.value)
    with pytest.raises(ValidationError) as excinfo:
        KazenEvent.model_validate(_base(cost_usd=float("inf")))
    assert "invalid_money" in str(excinfo.value)


def test_optional_lineage_preserved() -> None:
    dumped = canonicalize_event_dict(
        _base(
            tokens=17,
            run_id="run_p2",
            parent_run_id="run_parent",
            root_run_id="run_root",
            trace_id="trace_abc",
            step_id="step_p2",
        )
    )
    assert dumped["parent_run_id"] == "run_parent"
    assert dumped["root_run_id"] == "run_root"
    assert dumped["trace_id"] == "trace_abc"
    assert dumped["tokens_used"] == 17


def test_typed_usage_payload_survives() -> None:
    dumped = canonicalize_event_dict(
        _base(
            tokens=17,
            payload={
                "model": "fake-model",
                "usage": {
                    "input": 10,
                    "output": 7,
                    "cache_read": 0,
                    "cache_write": 0,
                    "reasoning": 0,
                },
                "usage_source": "provider",
                "confidence": 1.0,
            },
        )
    )
    assert dumped["payload"]["usage"]["input"] == 10
    assert dumped["payload"]["usage"]["output"] == 7
    assert dumped["tokens_used"] == 17


def test_canonicalize_event_dict_round_trip() -> None:
    dumped = canonicalize_event_dict(_base(tokens=17, run_id="run_p2"))
    assert dumped["tokens"] == 17
    assert dumped["tokens_used"] == 17
    assert dumped["root_run_id"] == "run_p2"
    again = canonicalize_event_dict(dumped)
    assert again["tokens_used"] == 17
    assert again["ts_ms"] == dumped["ts_ms"]


def test_finite_zero_cost_preserved() -> None:
    dumped = canonicalize_event_dict(_base(tokens=0, cost_usd=0.0))
    assert dumped["tokens_used"] == 0
    assert dumped["cost_usd"] == 0.0
    assert not math.isnan(dumped["cost_usd"])
