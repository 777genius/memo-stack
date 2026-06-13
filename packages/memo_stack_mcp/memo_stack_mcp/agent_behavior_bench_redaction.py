"""Redaction and truncation helpers for agent behavior benchmark reports."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from typing import Any

SENSITIVE_ENV_KEYS = (
    "MEMORY_AGENT_BENCH_OPENAI_API_KEY",
    "MEMORY_MCP_AUTH_TOKEN",
    "MEMORY_OPENAI_API_KEY",
    "MEMORY_SERVICE_TOKEN",
    "OPENAI_API_KEY",
)
SENSITIVE_KEY_NAMES = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "auth_token",
    "authtoken",
    "authorization",
    "bearer",
    "bearer_token",
    "credential",
    "credentials",
    "password",
    "secret",
    "session_token",
    "token",
}
SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{12,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{12,}\b"),
    re.compile(r"\bbench-secret-[A-Za-z0-9_.:-]+\b", re.IGNORECASE),
    re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password|passwd|credential)\s*[:=]\s*['\"]?"
        r"[A-Za-z0-9_./+=-]{8,}"
    ),
)


def _value(item: Any, key: str) -> Any:
    if isinstance(item, Mapping):
        return item.get(key)
    return getattr(item, key, None)


def _truncate_value(value: Any, *, max_chars: int) -> Any:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(text) <= max_chars:
        return value
    return {"truncated_json": _truncate_text(text, max_chars=max_chars)}


def _truncate_text(text: str, *, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20] + "...<truncated>"


def _redact_payload(value: Any, *, env: Mapping[str, str] | None = None) -> Any:
    if isinstance(value, str):
        return _redact_text(value, env=env)
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            safe_key = _redact_key(key, env=env)
            if isinstance(key, str) and _is_sensitive_key_name(key):
                redacted_item: Any = "<redacted>"
            else:
                redacted_item = _redact_payload(item, env=env)
            redacted[_dedupe_key(redacted, safe_key)] = redacted_item
        return redacted
    if isinstance(value, list):
        return [_redact_payload(item, env=env) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_payload(item, env=env) for item in value)
    return value


def _redact_key(key: Any, *, env: Mapping[str, str] | None = None) -> Any:
    if not isinstance(key, str):
        return key
    if _is_sensitive_key_name(key):
        return "<redacted-key>"
    redacted = _redact_text(key, env=env)
    return "<redacted-key>" if redacted != key else key


def _dedupe_key(mapping: Mapping[Any, Any], key: Any) -> Any:
    if key not in mapping:
        return key
    if not isinstance(key, str):
        return key
    index = 2
    while f"{key}-{index}" in mapping:
        index += 1
    return f"{key}-{index}"


def _redact_text(text: str, *, env: Mapping[str, str] | None = None) -> str:
    redacted = text
    for value in _sensitive_values(env):
        redacted = redacted.replace(value, "<redacted>")
    for key in SENSITIVE_ENV_KEYS:
        redacted = redacted.replace(key, "<redacted-env>")
    for pattern in SENSITIVE_TEXT_PATTERNS:
        redacted = pattern.sub("<redacted>", redacted)
    return redacted


def _is_sensitive_key_name(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "", key.lower())
    if not normalized:
        return False
    if normalized in {"secretredaction"}:
        return False
    if normalized.endswith(("count", "countzero", "rate", "ratemin080", "ratemin090")):
        return False
    if normalized in {re.sub(r"[^a-z0-9]+", "", item) for item in SENSITIVE_KEY_NAMES}:
        return True
    if normalized.endswith("apikey") or normalized.endswith("privatekey"):
        return True
    if normalized.endswith("token") and not normalized.endswith("budget"):
        return True
    return any(
        marker in normalized
        for marker in ("authorization", "credential", "password", "passwd", "secret")
    )


def _sensitive_values(env: Mapping[str, str] | None = None) -> list[str]:
    envs: list[Mapping[str, str]] = [os.environ]
    if env is not None:
        envs.append(env)
    values: set[str] = set()
    for item in envs:
        for key, value in item.items():
            if key.upper() in SENSITIVE_ENV_KEYS or _is_sensitive_key_name(key):
                stripped = str(value).strip()
                if len(stripped) >= 8:
                    values.add(stripped)
    return sorted(values, key=len, reverse=True)
