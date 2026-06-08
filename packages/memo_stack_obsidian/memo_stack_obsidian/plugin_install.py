"""Install the bundled Obsidian plugin into a vault."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any

PLUGIN_ID = "memo-stack"
PLUGIN_FILES = ("manifest.json", "main.js", "styles.css")
DEFAULT_OBSIDIAN_CONFIG_DIR = ".obsidian"


@dataclass(frozen=True)
class InstallPluginResult:
    target_dir: Path
    written: tuple[str, ...]
    skipped: tuple[str, ...]
    enabled: bool = False
    settings_path: Path | None = None


@dataclass
class InstallObsidianPluginUseCase:
    vault_path: Path
    obsidian_config_dir: str = DEFAULT_OBSIDIAN_CONFIG_DIR

    def execute(
        self,
        *,
        overwrite: bool = False,
        enable: bool = False,
        settings: dict[str, Any] | None = None,
    ) -> InstallPluginResult:
        vault = self.vault_path.expanduser().resolve()
        target_dir = plugin_dir(vault, self.obsidian_config_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        written: list[str] = []
        skipped: list[str] = []
        bundle_root = files("memo_stack_obsidian.plugin_bundle")
        for name in PLUGIN_FILES:
            target = target_dir / name
            if target.exists() and not overwrite:
                skipped.append(str(target))
                continue
            data = bundle_root.joinpath(name).read_bytes()
            _atomic_write_bytes(target, data)
            written.append(str(target))

        enabled = _enable_plugin(vault, self.obsidian_config_dir) if enable else False
        settings_path: Path | None = None
        if settings is not None:
            settings_path = target_dir / "data.json"
            if settings_path.exists() and not overwrite:
                skipped.append(str(settings_path))
            else:
                _write_plugin_settings(settings_path, settings)
                written.append(str(settings_path))

        return InstallPluginResult(
            target_dir=target_dir,
            written=tuple(written),
            skipped=tuple(skipped),
            enabled=enabled,
            settings_path=settings_path,
        )


def plugin_dir(vault: Path, obsidian_config_dir: str = DEFAULT_OBSIDIAN_CONFIG_DIR) -> Path:
    return resolve_obsidian_config_dir(vault, obsidian_config_dir) / "plugins" / PLUGIN_ID


def resolve_obsidian_config_dir(
    vault: Path,
    obsidian_config_dir: str = DEFAULT_OBSIDIAN_CONFIG_DIR,
) -> Path:
    raw = obsidian_config_dir.strip() or DEFAULT_OBSIDIAN_CONFIG_DIR
    relative = PurePosixPath(raw.replace("\\", "/"))
    if relative.is_absolute() or relative.as_posix() == "." or ".." in relative.parts:
        raise ValueError(f"Unsafe Obsidian config dir: {obsidian_config_dir}")
    resolved = (vault.expanduser().resolve() / Path(relative.as_posix())).resolve()
    vault_root = vault.expanduser().resolve()
    if resolved != vault_root and vault_root not in resolved.parents:
        raise ValueError(f"Obsidian config dir escapes vault: {obsidian_config_dir}")
    return resolved


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _enable_plugin(vault: Path, obsidian_config_dir: str) -> bool:
    obsidian_dir = resolve_obsidian_config_dir(vault, obsidian_config_dir)
    obsidian_dir.mkdir(parents=True, exist_ok=True)
    plugins_path = obsidian_dir / "community-plugins.json"
    plugins = _read_json_array(plugins_path)
    if PLUGIN_ID in plugins:
        return False
    plugins.append(PLUGIN_ID)
    _atomic_write_bytes(
        plugins_path,
        json.dumps(plugins, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    return True


def _write_plugin_settings(path: Path, settings: dict[str, Any]) -> None:
    existing = _read_json_object(path)
    merged = {**existing, **settings}
    if "token" not in merged:
        merged["token"] = ""
    _atomic_write_bytes(
        path,
        json.dumps(merged, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )


def _read_json_array(path: Path) -> list[str]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        raise ValueError(f"Expected JSON string array at {path}")
    return list(data)


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return dict(data)
