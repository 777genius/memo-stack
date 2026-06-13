"""Local filesystem blob storage adapter."""

from __future__ import annotations

import os
from pathlib import Path

from memo_stack_core.domain.errors import MemoryNotFoundError, MemoryValidationError
from memo_stack_core.ports.assets import StoredBlob


class LocalBlobStorage:
    def __init__(self, *, root_dir: str | Path) -> None:
        self._root = Path(root_dir).expanduser().resolve()

    async def write_bytes(self, *, storage_key: str, content: bytes) -> StoredBlob:
        path = self._path_for_key(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f".{path.name}.tmp")
        tmp_path.write_bytes(content)
        os.replace(tmp_path, path)
        return StoredBlob(storage_key=storage_key, byte_size=len(content))

    async def read_bytes(self, *, storage_key: str) -> bytes:
        path = self._path_for_key(storage_key)
        if not path.exists() or not path.is_file():
            raise MemoryNotFoundError("Asset blob not found")
        return path.read_bytes()

    async def delete(self, *, storage_key: str) -> None:
        path = self._path_for_key(storage_key)
        if path.exists() and path.is_file():
            path.unlink()

    def _path_for_key(self, storage_key: str) -> Path:
        normalized = storage_key.strip().replace("\\", "/")
        if not normalized or normalized.startswith("/") or ".." in normalized.split("/"):
            raise MemoryValidationError("Invalid storage key")
        path = (self._root / normalized).resolve()
        if self._root != path and self._root not in path.parents:
            raise MemoryValidationError("Invalid storage key")
        return path
