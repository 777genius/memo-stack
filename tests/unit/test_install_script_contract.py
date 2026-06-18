from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_install_script_dry_run_does_not_write_files(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(
        fake_bin / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                'if [ "$1" = "compose" ] && [ "$2" = "version" ]; then',
                "  exit 0",
                "fi",
                "exit 0",
                "",
            ]
        ),
    )
    _write_executable(fake_bin / "git", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(fake_bin / "python3", "#!/usr/bin/env bash\nexit 0\n")
    prefix = tmp_path / "memo-home"
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
    }

    result = subprocess.run(
        [
            "bash",
            "scripts/install.sh",
            "--dry-run",
            "--prefix",
            str(prefix),
            "--repo",
            "https://example.invalid/infinity-context.git",
            "--no-start",
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not prefix.exists()
    assert "dry-run:" in result.stdout


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
