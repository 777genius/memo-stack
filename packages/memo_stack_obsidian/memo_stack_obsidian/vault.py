"""Filesystem vault adapter."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath


class VaultPathError(ValueError):
    pass


class FilesystemVault:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def exists(self, relative_path: PurePosixPath) -> bool:
        return self._resolve(relative_path).exists()

    def write_text(self, relative_path: PurePosixPath, text: str) -> None:
        path = self._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        temp_path.replace(path)

    def delete_text(self, relative_path: PurePosixPath) -> None:
        self._resolve(relative_path).unlink(missing_ok=True)

    def read_text(self, relative_path: PurePosixPath) -> str:
        return self._resolve(relative_path).read_text(encoding="utf-8")

    def iter_markdown_files(self, relative_dir: PurePosixPath) -> Iterable[PurePosixPath]:
        directory = self._resolve(relative_dir)
        if not directory.exists():
            return ()
        paths: list[PurePosixPath] = []
        for path in sorted(directory.rglob("*.md")):
            if path.is_file():
                paths.append(PurePosixPath(path.relative_to(self.root).as_posix()))
        return tuple(paths)

    def _resolve(self, relative_path: PurePosixPath) -> Path:
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise VaultPathError(f"Unsafe vault path: {relative_path}")
        resolved = (self.root / Path(str(relative_path))).resolve()
        if self.root not in resolved.parents and resolved != self.root:
            raise VaultPathError(f"Path escapes vault: {relative_path}")
        return resolved
