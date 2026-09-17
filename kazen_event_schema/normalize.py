"""Event type normalization for cross-service KazenEvent ingest."""

from __future__ import annotations

_MODEL_CALL_ALIASES = frozenset({"model.call", "llm.call", "llm_call", "model_call"})


def normalize_event_type(event_type: str | None) -> str:
    """Map legacy aliases to canonical types."""
    et = str(event_type or "").strip()
    if et in ("llm.call", "llm_call"):
        return "model.call"
    return et


def is_model_call(event_type: str | None) -> bool:
    """True if this event represents an LLM/model invocation."""
    et = str(event_type or "").strip()
    if et in _MODEL_CALL_ALIASES:
        return True
    return normalize_event_type(et) == "model.call"
