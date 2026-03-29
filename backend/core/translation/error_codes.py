from __future__ import annotations


def classify_chunk_issue(error_summary: str | None) -> str | None:
    normalized = str(error_summary or "").strip().lower()
    if not normalized:
        return None
    if "429" in normalized or "rate limit" in normalized or "too many requests" in normalized:
        return "rate_limited"
    if "timeout" in normalized or "timed out" in normalized:
        return "timeout"
    if "invalid json" in normalized or "non json" in normalized:
        return "invalid_json"
    if "segment ids did not match" in normalized or "segment_id" in normalized and "match" in normalized:
        return "segment_id_mismatch"
    if "empty translation" in normalized:
        return "empty_translation"
    if "duplicated segment" in normalized:
        return "duplicate_segment"
    if "unexpected chunk translation payload" in normalized or "malformed chunk translation item" in normalized:
        return "malformed_payload"
    if "request failed" in normalized:
        return "request_error"
    return "unknown_error"
