from __future__ import annotations

import json
from pathlib import Path

from infinity_context_server import eval as eval_module
from infinity_context_server.memory_comparison_preflight import (
    MEMORY_COMPARISON_PREFLIGHT_SUITE,
    MemoryComparisonPreflightConfig,
    run_memory_comparison_preflight,
)


def test_memory_comparison_preflight_ready_for_locomo_fast(tmp_path: Path) -> None:
    dataset = tmp_path / "locomo-mini.json"
    dataset.write_text('[{"sample_id":"unit"}]', encoding="utf-8")

    result = run_memory_comparison_preflight(
        _config(
            dataset_path=dataset,
            env={"MEM0_API_KEY": "secret-mem0"},
        )
    )

    assert result["suite"] == MEMORY_COMPARISON_PREFLIGHT_SUITE
    assert result["ok"] is True
    assert result["status"] == "ok"
    assert result["safe_to_run_live"] is True
    assert result["ready_for_locomo_fast"] is True
    assert result["failed_checks"] == []
    assert result["warnings"] == []


def test_memory_comparison_preflight_reports_missing_required_gates(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "locomo-mini.json"
    dataset.write_text('[{"sample_id":"unit"}]', encoding="utf-8")

    result = run_memory_comparison_preflight(
        _config(
            dataset_path=dataset,
            allow_live=False,
            auth_token_configured=False,
            env={},
        )
    )

    assert result["ok"] is False
    assert result["safe_to_run_live"] is False
    assert result["ready_for_locomo_fast"] is False
    assert set(result["failed_checks"]) == {
        "allow_live_gate",
        "memo_auth_token_configured",
    }
    assert result["warnings"] == ["mem0_api_key_configured"]


def test_memory_comparison_preflight_gates_openai_without_leaking_keys(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "locomo-mini.json"
    dataset.write_text('[{"sample_id":"unit"}]', encoding="utf-8")
    result = run_memory_comparison_preflight(
        _config(
            dataset_path=dataset,
            answerer_provider="openai",
            answerer_model=None,
            allow_paid_llm=False,
            env={
                "MEM0_API_KEY": "secret-mem0-value",
                "MEMORY_OPENAI_API_KEY": "secret-openai-value",
            },
        )
    )

    serialized = json.dumps(result, sort_keys=True)
    assert result["ok"] is False
    assert result["safe_to_run_paid_llm"] is False
    assert "paid_llm_gate" in result["failed_checks"]
    assert "openai_answerer_model_configured" in result["failed_checks"]
    assert "secret-mem0-value" not in serialized
    assert "secret-openai-value" not in serialized


def test_memory_comparison_preflight_flags_full_case_set_not_fast_ready(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "locomo-mini.json"
    dataset.write_text('[{"sample_id":"unit"}]', encoding="utf-8")

    result = run_memory_comparison_preflight(
        _config(
            dataset_path=dataset,
            case_set="all",
            report_mode="full",
            env={"MEM0_API_KEY": "secret-mem0"},
        )
    )

    assert result["ok"] is True
    assert result["safe_to_run_live"] is True
    assert result["ready_for_locomo_fast"] is False
    assert set(result["fast_readiness_blockers"]) == {
        "locomo_fast_case_set",
        "compact_report_mode",
    }


def test_memory_comparison_preflight_cli_prints_sanitized_json(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "locomo-mini.json"
    dataset.write_text('[{"sample_id":"unit"}]', encoding="utf-8")
    monkeypatch.setenv("MEMORY_SERVICE_TOKEN", "secret-service-token")
    monkeypatch.setenv("MEM0_API_KEY", "secret-mem0-token")

    eval_module.main(
        [
            "memory-comparison-benchmark",
            "--dataset",
            str(dataset),
            "--memo-api-url",
            "http://memo.example",
            "--mem0-url",
            "http://mem0.example",
            "--allow-live",
            "--case-set",
            "locomo-fast",
            "--locomo-ingest-mode",
            "official-turns",
            "--report-mode",
            "compact",
            "--top-k",
            "200",
            "--preflight-only",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["suite"] == MEMORY_COMPARISON_PREFLIGHT_SUITE
    assert payload["ok"] is True
    assert payload["ready_for_locomo_fast"] is True
    assert "secret-service-token" not in captured.out
    assert "secret-mem0-token" not in captured.out
    assert "secret-service-token" not in captured.err
    assert "secret-mem0-token" not in captured.err


def _config(
    *,
    dataset_path: Path,
    case_set: str = "locomo-fast",
    locomo_ingest_mode: str = "official-turns",
    report_mode: str = "compact",
    top_k: int = 200,
    top_k_cutoffs: tuple[int, ...] = (10, 20, 50, 200),
    allow_live: bool = True,
    allow_paid_llm: bool = False,
    answerer_provider: str = "deterministic",
    judge_provider: str = "deterministic",
    answerer_model: str | None = None,
    judge_model: str | None = None,
    auth_token_configured: bool = True,
    env: dict[str, str] | None = None,
) -> MemoryComparisonPreflightConfig:
    return MemoryComparisonPreflightConfig(
        dataset_path=dataset_path,
        memo_api_url="http://memo.example",
        mem0_url="http://mem0.example",
        case_set=case_set,
        locomo_ingest_mode=locomo_ingest_mode,
        report_mode=report_mode,
        top_k=top_k,
        top_k_cutoffs=top_k_cutoffs,
        allow_live=allow_live,
        allow_paid_llm=allow_paid_llm,
        answerer_provider=answerer_provider,
        judge_provider=judge_provider,
        answerer_model=answerer_model,
        judge_model=judge_model,
        openai_api_key_env="MEMORY_OPENAI_API_KEY",
        mem0_api_key_env="MEM0_API_KEY",
        auth_token_configured=auth_token_configured,
        env=env or {},
    )
