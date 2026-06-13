import importlib.util
import sys
from pathlib import Path
from typing import Any


def load_smoke_module():
    path = Path(__file__).parents[2] / "examples" / "integration_memory_smoke.py"
    spec = importlib.util.spec_from_file_location("integration_memory_smoke", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeSmokeClient:
    def __init__(self, *, leak_after_forget: bool = False) -> None:
        self.calls: list[str] = []
        self.leak_after_forget = leak_after_forget
        self.forgotten = False

    def health(self) -> dict[str, Any]:
        self.calls.append("health")
        return {"status": "ok"}

    def create_space(self, **_kwargs: Any) -> dict[str, Any]:
        self.calls.append("create_space")
        return {"data": {"id": "space_smoke"}}

    def create_memory_scope(self, **_kwargs: Any) -> dict[str, Any]:
        self.calls.append("create_memory_scope")
        return {"data": {"id": "memory_scope_default"}}

    def remember_fact(self, **_kwargs: Any) -> dict[str, Any]:
        self.calls.append("remember_fact")
        return {"data": {"id": "fact_smoke", "version": 1}}

    def update_fact(self, *_args: Any, **kwargs: Any) -> dict[str, Any]:
        self.calls.append("update_fact")
        return {"data": {"id": "fact_smoke", "version": kwargs["expected_version"] + 1}}

    def ingest_document(self, **_kwargs: Any) -> dict[str, Any]:
        self.calls.append("ingest_document")
        return {"data": {"id": "doc_smoke"}}

    def search(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append("search")
        return {"data": {"items": [{"text": kwargs["query"]}]}}

    def build_context(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append("build_context")
        query = str(kwargs["query"])
        if self.forgotten and not self.leak_after_forget:
            rendered_text = ""
            items: list[dict[str, Any]] = []
        else:
            rendered_text = query
            items = [{"text": query}]
        return {"data": {"rendered_text": rendered_text, "items": items}}

    def forget_fact(self, _fact_id: str) -> dict[str, Any]:
        self.calls.append("forget_fact")
        self.forgotten = True
        return {"data": {"id": "fact_smoke", "status": "deleted"}}


def test_integration_smoke_uses_sdk_happy_path() -> None:
    smoke = load_smoke_module()
    client = FakeSmokeClient()
    config = smoke.SmokeConfig(
        api_url="http://memory.test",
        auth_token="test-token",
        space_slug="memo-stack-smoke",
        memory_scope_external_ref="default",
        thread_external_ref="smoke-test",
        run_id="unit",
        timeout=1,
    )

    result = smoke.run_smoke(client, config)

    assert result["ok"] is True
    assert result["api_url"] == "http://memory.test"
    assert result["fact_id"] == "fact_smoke"
    assert client.calls == [
        "health",
        "create_space",
        "create_memory_scope",
        "remember_fact",
        "update_fact",
        "ingest_document",
        "search",
        "build_context",
        "forget_fact",
        "build_context",
    ]


def test_integration_smoke_fails_when_forgotten_fact_leaks() -> None:
    smoke = load_smoke_module()
    client = FakeSmokeClient(leak_after_forget=True)
    config = smoke.SmokeConfig(
        api_url="http://memory.test",
        auth_token="test-token",
        space_slug="memo-stack-smoke",
        memory_scope_external_ref="default",
        thread_external_ref="smoke-test",
        run_id="unit",
        timeout=1,
    )

    try:
        smoke.run_smoke(client, config)
    except smoke.SmokeFailure as exc:
        assert "Forgotten fact leaked" in str(exc)
    else:
        raise AssertionError("Expected smoke failure")
