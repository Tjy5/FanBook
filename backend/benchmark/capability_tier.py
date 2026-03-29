from __future__ import annotations

from backend.core.translation.runtime_settings import (
    normalize_api_mode,
    normalize_reasoning_mode,
    normalize_structured_output_strength,
)


def derive_capability_tier(
    *,
    api_mode: object = None,
    reasoning_mode: object = None,
    structured_output_strength: object = None,
    detected_context_window: object = None,
    max_requests_per_minute: object = None,
) -> str:
    api_bucket = normalize_api_mode(api_mode) or "unknown_api"
    reasoning_bucket = _reasoning_bucket(reasoning_mode)
    structured_bucket = _structured_output_bucket(structured_output_strength)
    context_bucket = _context_window_bucket(detected_context_window)
    rate_bucket = _rate_limit_bucket(max_requests_per_minute)
    return "__".join(
        (
            api_bucket,
            reasoning_bucket,
            structured_bucket,
            context_bucket,
            rate_bucket,
        )
    )


def _reasoning_bucket(value: object) -> str:
    normalized = normalize_reasoning_mode(value)
    if normalized is None:
        return "unknown_reasoning"
    if normalized == "reasoning":
        return "reasoning"
    return f"{normalized}_reasoning"


def _structured_output_bucket(value: object) -> str:
    normalized = normalize_structured_output_strength(value)
    if normalized is None:
        return "unknown_structured"
    return f"{normalized}_structured"


def _context_window_bucket(value: object) -> str:
    try:
        normalized = int(value) if value is not None else None
    except (TypeError, ValueError):
        normalized = None
    if normalized is None or normalized <= 0:
        return "unknown_context"
    if normalized >= 400000:
        return "xl_context"
    if normalized >= 128000:
        return "large_context"
    if normalized >= 32000:
        return "medium_context"
    if normalized >= 16000:
        return "entry_large_context"
    return "compact_context"


def _rate_limit_bucket(value: object) -> str:
    try:
        normalized = int(value) if value is not None else None
    except (TypeError, ValueError):
        normalized = None
    if normalized is None or normalized <= 0:
        return "unknown_rate"
    if normalized <= 10:
        return "strict_rate_limit"
    if normalized <= 30:
        return "moderate_rate_limit"
    return "standard_rate"
