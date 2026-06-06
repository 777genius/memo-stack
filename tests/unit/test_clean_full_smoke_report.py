import json

import pytest

from scripts.clean_full_smoke import CleanSmokeFailure, _emit_report, _write_report_out


def test_clean_full_smoke_writes_redacted_report_out(tmp_path, monkeypatch, capsys) -> None:
    report = tmp_path / "reports" / "full-provider.json"
    token = "clean-smoke-secret-token-value"
    monkeypatch.setenv("MEMORY_CLEAN_SMOKE_REPORT_OUT", str(report))
    monkeypatch.setenv("MEMORY_CLEAN_SMOKE_TOKEN", token)

    _emit_report(
        {
            "suite": "memo-stack-full-provider-canary",
            "ok": True,
            "token": token,
            "checks": {"providers_are_healthy": True},
            "message": f"Bearer {token}",
        },
        env={"MEMORY_CLEAN_SMOKE_TOKEN": token},
    )

    stdout = capsys.readouterr().out
    report_text = report.read_text(encoding="utf-8")
    payload = json.loads(report_text)

    assert payload["suite"] == "memo-stack-full-provider-canary"
    assert payload["ok"] is True
    assert token not in stdout
    assert token not in report_text
    assert f"Bearer {token}" not in report_text
    assert "<redacted-key>" in payload


def test_clean_full_smoke_report_out_rejects_unredacted_secret(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MEMORY_CLEAN_SMOKE_REPORT_OUT", str(tmp_path / "unsafe.json"))

    with pytest.raises(CleanSmokeFailure, match="unredacted secret"):
        _write_report_out('{"leak": "sk-test_12345678901234567890"}')
