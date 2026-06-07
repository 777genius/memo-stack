"""Report emission helpers for clean full-provider smoke."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, TextIO

try:
    from scripts.clean_full_smoke_redaction import has_unredacted_secret_marker, redact_payload
except ModuleNotFoundError:
    from clean_full_smoke_redaction import has_unredacted_secret_marker, redact_payload


def emit_report(
    payload: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    stream: TextIO | None = None,
    failure_cls: type[Exception] = RuntimeError,
) -> None:
    serialized = json.dumps(
        redact_payload(payload, env=env),
        ensure_ascii=False,
        sort_keys=True,
    )
    write_report_out(serialized, failure_cls=failure_cls)
    print(serialized, file=stream or sys.stdout)


def write_report_out(
    serialized: str,
    *,
    failure_cls: type[Exception] = RuntimeError,
    getenv: Callable[[str, str], str] = os.getenv,
) -> None:
    report_out = getenv("MEMORY_CLEAN_SMOKE_REPORT_OUT", "").strip()
    if not report_out:
        return
    if has_unredacted_secret_marker(serialized):
        raise failure_cls("Refusing to write clean smoke report with unredacted secret markers")
    path = Path(report_out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized, encoding="utf-8")
