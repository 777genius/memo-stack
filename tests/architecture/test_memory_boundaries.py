"""Static architecture checks for Memory Platform package boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _python_files(package: str) -> list[Path]:
    return sorted((REPO_ROOT / package).rglob("*.py"))


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def _assert_no_imports(package: str, forbidden_roots: set[str]) -> None:
    violations: list[str] = []
    for path in _python_files(package):
        for imported in sorted(_imports(path)):
            root = imported.split(".", 1)[0]
            if root in forbidden_roots:
                rel = path.relative_to(REPO_ROOT)
                violations.append(f"{rel}: imports {imported}")

    assert not violations, "Forbidden architecture imports:\n" + "\n".join(violations)


def test_memory_core_has_no_infrastructure_dependencies() -> None:
    _assert_no_imports(
        "packages/memory_core/memory_core",
        {
            "anthropic",
            "fastapi",
            "graphiti",
            "httpx",
            "memory_adapters",
            "memory_mcp",
            "memory_server",
            "mcp",
            "openai",
            "qdrant_client",
            "sqlalchemy",
        },
    )


def test_memory_adapters_do_not_depend_on_api_or_mcp_layers() -> None:
    _assert_no_imports(
        "packages/memory_adapters/memory_adapters",
        {
            "fastapi",
            "memory_mcp",
            "memory_server",
            "mcp",
        },
    )


def test_memory_mcp_does_not_depend_on_server_adapters_or_providers() -> None:
    _assert_no_imports(
        "packages/memory_mcp/memory_mcp",
        {
            "anthropic",
            "fastapi",
            "graphiti",
            "memory_adapters",
            "memory_server",
            "openai",
            "qdrant_client",
            "sqlalchemy",
        },
    )


def test_memory_sdk_stays_transport_client_only() -> None:
    _assert_no_imports(
        "packages/memory_sdk/memory_sdk",
        {
            "anthropic",
            "fastapi",
            "graphiti",
            "memory_adapters",
            "memory_core",
            "memory_mcp",
            "memory_server",
            "mcp",
            "openai",
            "qdrant_client",
            "sqlalchemy",
        },
    )
