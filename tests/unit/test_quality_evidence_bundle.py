from __future__ import annotations

import json
from pathlib import Path

from memo_stack_server.evidence_bundle import build_quality_evidence_bundle


def test_quality_evidence_bundle_writes_scorecard_artifacts(tmp_path: Path) -> None:
    result = build_quality_evidence_bundle(output_dir=tmp_path)

    report_names = {Path(item["report_path"]).name for item in result["deterministic_reports"]}

    assert result["ok"] is True
    assert result["scorecard"]["maturity_score_10"] == 10.0
    assert result["scorecard"]["confidence_tier"] == "internal_deterministic"
    assert result["scorecard"]["top_library_comparison_ready"] is False
    assert report_names == {
        "small-golden.json",
        "quality-golden.json",
        "long-memory-golden.json",
        "auto-memory-golden.json",
        "graph-native-golden.json",
        "prompt-contract.json",
    }
    assert (tmp_path / "memory-quality-scorecard.json").exists()
    assert (tmp_path / "quality-evidence-bundle.json").exists()
    assert json.loads((tmp_path / "quality-evidence-bundle.json").read_text())["ok"] is True


def test_quality_evidence_bundle_requires_existing_extra_reports(tmp_path: Path) -> None:
    missing = tmp_path / "missing-full-provider.json"

    try:
        build_quality_evidence_bundle(output_dir=tmp_path, extra_report_paths=(missing,))
    except ValueError as exc:
        assert "Evidence extra report does not exist" in str(exc)
    else:
        raise AssertionError("expected missing extra report to fail")
