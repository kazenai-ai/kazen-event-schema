"""Tests for event type normalization."""

from kazen_event_schema import is_model_call, normalize_event_type


def test_normalize_llm_call_alias() -> None:
    assert normalize_event_type("llm.call") == "model.call"
    assert normalize_event_type("llm_call") == "model.call"
    assert normalize_event_type("model.call") == "model.call"


def test_is_model_call() -> None:
    assert is_model_call("model.call")
    assert is_model_call("llm.call")
    assert not is_model_call("tool.call")
