"""Safe provider exception diagnostics for adapter boundaries."""

from __future__ import annotations


def classify_provider_exception(
    exc: Exception,
    *,
    prefix: str,
    default_code: str,
) -> tuple[str, bool]:
    status_code = getattr(exc, "status_code", None)
    error_code = _provider_error_value(exc, "code")
    error_type = _provider_error_value(exc, "type")
    class_name = exc.__class__.__name__.lower()

    if status_code == 402 or error_code in {
        "billing_hard_limit_reached",
        "insufficient_quota",
        "quota_exceeded",
    } or error_type in {
        "billing_hard_limit_reached",
        "insufficient_quota",
        "quota_exceeded",
    }:
        return f"{prefix}.quota_exceeded", False
    if status_code == 401 or "authentication" in class_name or error_code == "invalid_api_key":
        return f"{prefix}.invalid_api_key", False
    if status_code == 403 or "permissiondenied" in class_name or error_code == "permission_denied":
        return f"{prefix}.permission_denied", False
    if status_code == 429 or "ratelimit" in class_name or "rate_limit" in error_code:
        return f"{prefix}.rate_limited", True
    if status_code in {400, 404} or "badrequest" in class_name or error_code in {
        "model_not_found",
        "invalid_request_error",
    }:
        return f"{prefix}.invalid_request", False
    if (
        "timeout" in class_name
        or status_code == 408
        or error_code in {"timeout", "timed_out", "request_timeout"}
        or error_type in {"timeout", "timed_out", "request_timeout"}
    ):
        return f"{prefix}.timeout", True
    if "connection" in class_name or status_code in {409, 500, 502, 503, 504}:
        return f"{prefix}.provider_unavailable", True
    return default_code, True


def _provider_error_value(exc: Exception, name: str) -> str:
    raw = getattr(exc, name, None)
    if isinstance(raw, str) and raw:
        return raw.lower()

    for container_name in ("error", "body"):
        container = getattr(exc, container_name, None)
        value = _nested_error_value(container, name)
        if value:
            return value
    return ""


def _nested_error_value(value: object, name: str) -> str:
    if isinstance(value, dict):
        nested = value.get(name)
        if isinstance(nested, str) and nested:
            return nested.lower()
        error = value.get("error")
        if isinstance(error, dict):
            nested = error.get(name)
            if isinstance(nested, str) and nested:
                return nested.lower()
    return ""
