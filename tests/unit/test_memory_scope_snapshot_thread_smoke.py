from __future__ import annotations

import importlib.util
import sys
import urllib.error
from io import BytesIO
from pathlib import Path
from typing import Any


def load_smoke_module():
    path = Path(__file__).parents[2] / "scripts" / "memory_scope_snapshot_thread_smoke.py"
    spec = importlib.util.spec_from_file_location("memory_scope_snapshot_thread_smoke", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeSnapshotThreadSmokeApi:
    def __init__(self, *, restored_target_id: str = "thread_restored") -> None:
        self.restored_target_id = restored_target_id
        self.calls: list[tuple[str, str]] = []

    def request(
        self,
        method: str,
        path: str,
        _config: Any,
        body: dict[str, Any] | None,
        params: dict[str, str] | None,
    ) -> dict[str, Any]:
        self.calls.append((method, path))
        if (method, path) == ("GET", "/v1/health"):
            return {"status": "ok"}
        if (method, path) == ("POST", "/v1/captures"):
            assert body is not None
            assert body["thread_external_ref"] == "snapshot-thread"
            return {"data": {"id": "capture_source"}}
        if (method, path) == ("POST", "/v1/link-suggestions"):
            assert body is not None
            assert body["persist"] is True
            return {
                "data": {
                    "candidates": [
                        {
                            "target_type": "thread",
                            "target_id": "thread_source",
                            "suggestion_id": "ctxlinksug_source",
                            "metadata": {"external_ref": "snapshot-thread"},
                        }
                    ]
                }
            }
        if (method, path) == ("GET", "/v1/export/memory_scope-snapshot"):
            assert params is not None
            assert params["redacted"] == "false"
            return {
                "data": {
                    "schema_version": 9,
                    "threads": [{"id": "thread_source", "external_ref": "snapshot-thread"}],
                    "context_link_suggestions": [
                        {
                            "id": "ctxlinksug_source",
                            "target_type": "thread",
                            "target_id": "thread_source",
                        }
                    ],
                },
                "counts": {"threads": 1},
                "manifest": {"snapshot_sha256": "hash"},
            }
        if (method, path) == ("POST", "/v1/export/memory_scope-snapshot/import"):
            assert body is not None
            assert body["merge_strategy"] == "create_new_memory_scope"
            assert body["confirmed"] is True
            return {
                "data": {
                    "status": "ok",
                    "imported": {"threads": 1, "context_link_suggestions": 1},
                    "created_memory_scope": {"external_ref": "restored-scope"},
                }
            }
        if (method, path) == ("GET", "/v1/memory-browser"):
            assert params is not None
            assert params["suggestion_status"] == "pending"
            return {
                "data": {
                    "threads": [{"id": "thread_restored", "external_ref": "snapshot-thread"}],
                    "context_link_suggestions": [
                        {
                            "id": "ctxlinksug_restored",
                            "target_type": "thread",
                            "target_id": self.restored_target_id,
                        }
                    ],
                }
            }
        if method == "POST" and path == "/v1/context-link-suggestions/ctxlinksug_restored/review":
            assert body == {"action": "approve", "reason": "snapshot thread smoke"}
            return {
                "data": {
                    "suggestion": {"status": "approved"},
                    "link": {"target_type": "thread", "target_id": "thread_restored"},
                }
            }
        raise AssertionError(f"Unexpected request: {method} {path}")


def test_snapshot_thread_smoke_runs_portable_thread_flow() -> None:
    smoke = load_smoke_module()
    api = FakeSnapshotThreadSmokeApi()
    config = smoke.SmokeConfig(api_url="http://memory.test", auth_token="token")

    result = smoke.run_smoke(config, request_json=api.request, time_ns=lambda: 42)

    assert result == {
        "status": "ok",
        "api_url": "http://memory.test",
        "space_slug": "snapshot-thread-smoke-42",
        "source_memory_scope": "source-memory-scope",
        "restored_memory_scope": "restored-scope",
        "source_thread_id": "thread_source",
        "restored_thread_id": "thread_restored",
        "approved_suggestion_id": "ctxlinksug_restored",
    }
    assert api.calls == [
        ("GET", "/v1/health"),
        ("POST", "/v1/captures"),
        ("POST", "/v1/link-suggestions"),
        ("GET", "/v1/export/memory_scope-snapshot"),
        ("POST", "/v1/export/memory_scope-snapshot/import"),
        ("GET", "/v1/memory-browser"),
        ("POST", "/v1/context-link-suggestions/ctxlinksug_restored/review"),
    ]


def test_snapshot_thread_smoke_fails_when_suggestion_target_is_not_remapped() -> None:
    smoke = load_smoke_module()
    api = FakeSnapshotThreadSmokeApi(restored_target_id="thread_source")
    config = smoke.SmokeConfig(api_url="http://memory.test", auth_token="token")

    try:
        smoke.run_smoke(config, request_json=api.request, time_ns=lambda: 42)
    except smoke.SmokeFailure as exc:
        assert "Restored thread suggestion target did not remap" in str(exc)
    else:
        raise AssertionError("Expected SmokeFailure")


def test_snapshot_thread_smoke_http_error_redacts_auth_token(
    monkeypatch,
) -> None:
    smoke = load_smoke_module()
    token = "snapshot-secret-token-abcdefghijklmnopqrstuvwxyz"
    config = smoke.SmokeConfig(api_url="http://memory.test", auth_token=token)

    def fail_urlopen(*_args: Any, **_kwargs: Any) -> Any:
        raise urllib.error.HTTPError(
            url="http://memory.test/v1/health",
            code=500,
            msg="failed",
            hdrs={},
            fp=BytesIO(f'{{"message":"Bearer {token}"}}'.encode()),
        )

    monkeypatch.setattr(smoke.urllib.request, "urlopen", fail_urlopen)

    try:
        smoke._request_json("GET", "/v1/health", config, None, None)
    except smoke.SmokeFailure as exc:
        message = str(exc)
        assert token not in message
        assert "<redacted>" in message
    else:
        raise AssertionError("Expected SmokeFailure")
