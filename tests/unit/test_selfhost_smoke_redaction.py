from __future__ import annotations

import importlib.util
import os
import sys
import urllib.error
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest


def load_smoke_module() -> Any:
    path = Path(__file__).parents[2] / "scripts" / "selfhost_smoke.py"
    spec = importlib.util.spec_from_file_location("selfhost_smoke", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_selfhost_smoke_run_failure_redacts_sensitive_env_values() -> None:
    smoke = load_smoke_module()
    token = "selfhost-secret-token-1234567890"
    env = dict(os.environ)
    env["MEMORY_SERVICE_TOKEN"] = token

    with pytest.raises(smoke.SmokeFailure) as exc:
        smoke._run(
            [
                sys.executable,
                "-c",
                "import os, sys; print(os.environ['MEMORY_SERVICE_TOKEN']); sys.exit(7)",
            ],
            env=env,
            timeout=10,
        )

    message = str(exc.value)
    assert token not in message
    assert "<redacted>" in message


def test_selfhost_smoke_http_error_redacts_response_body_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    smoke = load_smoke_module()
    token = "selfhost-secret-token-abcdefghijklmnopqrstuvwxyz"

    def fail_urlopen(*_args: Any, **_kwargs: Any) -> Any:
        raise urllib.error.HTTPError(
            url="http://memory.test/v1/health",
            code=500,
            msg="failed",
            hdrs={},
            fp=BytesIO(f'{{"message":"Bearer {token}"}}'.encode()),
        )

    monkeypatch.setattr(smoke.urllib.request, "urlopen", fail_urlopen)

    with pytest.raises(smoke.SmokeFailure) as exc:
        smoke._request_json(
            "GET",
            "http://memory.test/v1/health",
            token=token,
            timeout=1,
        )

    message = str(exc.value)
    assert token not in message
    assert "<redacted>" in message
