from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from memo_stack_server import eval as eval_module
from memo_stack_server import evidence_bundle


def test_eval_scorecard_cli_redacts_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_secret = "sk-proj-secretvalue1234567890"

    def fail_scorecard(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise ValueError(f"scorecard failed with {raw_secret}")

    monkeypatch.setattr(eval_module, "run_memory_quality_scorecard", fail_scorecard)

    with pytest.raises(SystemExit) as exc:
        eval_module.main(["scorecard"])

    message = str(exc.value)
    assert raw_secret not in message
    assert "[redacted]" in message


def test_evidence_bundle_cli_redacts_validation_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    raw_secret = "sk-proj-secretvalue1234567890"

    def fail_bundle(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise ValueError(f"bundle failed with {raw_secret}")

    monkeypatch.setattr(evidence_bundle, "build_quality_evidence_bundle", fail_bundle)

    with pytest.raises(SystemExit) as exc:
        evidence_bundle.main(["--output-dir", str(tmp_path)])

    message = str(exc.value)
    assert raw_secret not in message
    assert "[redacted]" in message
