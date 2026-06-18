"""File size boundaries for maintainable Clean Architecture modules."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

CODE_GLOBS = ("*.py", "*.js", "*.ts", "*.tsx", "*.rs")
CODE_ROOTS = ("packages", "scripts", "tests")
IGNORED_PATH_PARTS = {
    "__pycache__",
    "node_modules",
}

MAX_LINES = 2500
IDEAL_LINES = 1000

LEGACY_OVER_MAX_ALLOWLIST = {
    "packages/infinity_context_server/infinity_context_server/web/assets/memory-browser.js",
    "tests/unit/test_asset_context_links_api.py",
    "tests/unit/test_asset_extractions_api.py",
    "tests/unit/test_sdk_contract.py",
}

IDEAL_OVER_1000_DEBT_ALLOWLIST = {
    *LEGACY_OVER_MAX_ALLOWLIST,
    "packages/infinity_context_core/infinity_context_core/application/dto.py",
    "packages/infinity_context_core/infinity_context_core/application/use_cases/asset_extractions.py",
    "packages/infinity_context_core/infinity_context_core/domain/entities.py",
    "packages/infinity_context_adapters/infinity_context_adapters/extraction/content.py",
    "packages/infinity_context_adapters/infinity_context_adapters/postgres/mappers.py",
    "packages/infinity_context_adapters/infinity_context_adapters/postgres/repositories.py",
    "packages/infinity_context_sdk/infinity_context_sdk/__init__.py",
    "packages/infinity_context_mcp/infinity_context_mcp/agent_behavior_bench.py",
    "packages/infinity_context_mcp/infinity_context_mcp/application/service.py",
    "packages/infinity_context_mcp/infinity_context_mcp/plugin_hook.py",
    "packages/infinity_context_mcp/infinity_context_mcp/server.py",
    "packages/infinity_context_server/infinity_context_server/admin.py",
    "packages/infinity_context_server/infinity_context_server/eval.py",
    "packages/infinity_context_server/infinity_context_server/eval_auto_memory.py",
    "packages/infinity_context_server/infinity_context_server/eval_scorecard.py",
    "packages/infinity_context_server/infinity_context_server/eval_semantic_linking.py",
    "packages/infinity_context_server/infinity_context_server/public_benchmark.py",
    "packages/infinity_context_server/infinity_context_server/web/assets/memory-browser.js",
    "scripts/clean_full_smoke.py",
    "scripts/multimodal_docker_live_proof.py",
    "tests/e2e/test_memory_scale_chaos_load_e2e.py",
    "tests/unit/test_admin_tokens.py",
    "tests/unit/test_agent_behavior_bench.py",
    "tests/unit/test_anchor_lifecycle_api.py",
    "tests/unit/test_asset_context_links_api.py",
    "tests/unit/test_asset_extractions_api.py",
    "tests/unit/test_capture_worker.py",
    "tests/unit/test_content_extraction_adapters.py",
    "tests/unit/test_context_provider_consistency.py",
    "tests/unit/test_legacy_and_context_api.py",
    "tests/unit/test_local_runbook.py",
    "tests/unit/test_mcp_adapter.py",
    "tests/unit/test_memory_scope_snapshot_api.py",
    "tests/unit/test_provider_adapters.py",
    "tests/unit/test_quality_evidence_bundle.py",
    "tests/unit/test_schema_migrations.py",
    "tests/unit/test_sdk_contract.py",
    "tests/unit/test_worker_eval.py",
    "tests/unit/test_worker_eval_scorecard.py",
}


def test_no_new_file_exceeds_hard_2500_line_ceiling() -> None:
    offenders = [
        f"{relative_path}: {line_count} lines"
        for relative_path, line_count in _code_file_line_counts()
        if line_count > MAX_LINES and relative_path not in LEGACY_OVER_MAX_ALLOWLIST
    ]

    assert offenders == []


def test_files_over_ideal_1000_line_target_are_explicit_debt() -> None:
    offenders = [
        f"{relative_path}: {line_count} lines"
        for relative_path, line_count in _code_file_line_counts()
        if line_count > IDEAL_LINES and relative_path not in IDEAL_OVER_1000_DEBT_ALLOWLIST
    ]

    assert offenders == []


def _code_file_line_counts() -> list[tuple[str, int]]:
    results: list[tuple[str, int]] = []
    for root_name in CODE_ROOTS:
        root = REPO_ROOT / root_name
        if not root.exists():
            continue
        for glob in CODE_GLOBS:
            for path in root.rglob(glob):
                if IGNORED_PATH_PARTS.intersection(path.parts):
                    continue
                relative_path = path.relative_to(REPO_ROOT).as_posix()
                results.append((relative_path, _line_count(path)))
    return sorted(results)


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())
