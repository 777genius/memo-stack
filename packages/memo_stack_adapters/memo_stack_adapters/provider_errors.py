"""Safe provider exception diagnostics for adapter boundaries."""

from __future__ import annotations


def classify_provider_exception(
    exc: Exception,
    *,
    prefix: str,
    default_code: str,
) -> tuple[str, bool]:
    status_code = getattr(exc, "status_code", None)
    error_code = str(getattr(exc, "code", "") or "").lower()
    class_name = exc.__class__.__name__.lower()

    if status_code == 401 or "authentication" in class_name or error_code == "invalid_api_key":
        return f"{prefix}.invalid_api_key", False
    if status_code == 429 or "ratelimit" in class_name or "rate_limit" in error_code:
        return f"{prefix}.rate_limited", True
    if status_code in {400, 404} or "badrequest" in class_name or error_code in {
        "model_not_found",
        "invalid_request_error",
    }:
        return f"{prefix}.invalid_request", False
    if (
        "timeout" in class_name
        or "connection" in class_name
        or status_code in {408, 409, 500, 502, 503, 504}
    ):
        return f"{prefix}.provider_unavailable", True
    return default_code, True
