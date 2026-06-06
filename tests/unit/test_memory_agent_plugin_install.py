import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[2]
SCRIPT_PATH = ROOT / "scripts" / "install_memory_agent_plugin.py"


def test_memory_agent_plugin_install_detects_managed_state(tmp_path, monkeypatch) -> None:
    module = _load_script()
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps({"installations": [{"integration_id": "memory-agent-plugin"}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("PLUGIN_KIT_AI_STATE_PATH", str(state_path))

    assert module.is_managed() is True


def test_memory_agent_plugin_install_detects_missing_state(tmp_path, monkeypatch) -> None:
    module = _load_script()
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"installations": []}), encoding="utf-8")
    monkeypatch.setenv("PLUGIN_KIT_AI_STATE_PATH", str(state_path))

    assert module.is_managed() is False


def test_memory_agent_plugin_install_uses_update_when_managed(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    module = _load_script()
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps({"installations": [{"integration_id": "memory-agent-plugin"}]}),
        encoding="utf-8",
    )
    calls: list[list[str]] = []
    monkeypatch.setenv("PLUGIN_KIT_AI_STATE_PATH", str(state_path))
    monkeypatch.setattr(module.subprocess, "call", lambda argv, cwd: calls.append(argv) or 0)
    monkeypatch.setattr(module.sys, "argv", ["install_memory_agent_plugin.py", "--dry-run"])

    assert module.main() == 0

    assert calls == [[str(module.PLUGIN_KIT), "update", "memory-agent-plugin", "--dry-run"]]
    assert "memory-agent-plugin update" in capsys.readouterr().err


def test_memory_agent_plugin_install_uses_add_when_missing(tmp_path, monkeypatch) -> None:
    module = _load_script()
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"installations": []}), encoding="utf-8")
    calls: list[list[str]] = []
    monkeypatch.setenv("PLUGIN_KIT_AI_STATE_PATH", str(state_path))
    monkeypatch.setattr(module.subprocess, "call", lambda argv, cwd: calls.append(argv) or 0)
    monkeypatch.setattr(module.sys, "argv", ["install_memory_agent_plugin.py"])

    assert module.main() == 0

    assert calls
    command = calls[0]
    assert command[:3] == [str(module.PLUGIN_KIT), "add", str(module.PLUGIN_ROOT)]
    target_pairs = list(zip(command[3::2], command[4::2], strict=True))
    assert target_pairs == [("--target", target) for target in module.INSTALL_TARGETS]


def _load_script() -> Any:
    spec = importlib.util.spec_from_file_location(
        "install_memory_agent_plugin_for_test",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
