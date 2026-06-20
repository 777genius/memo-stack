"""Shared storage-key safety policy for maintenance use cases."""

from __future__ import annotations


def is_safe_blob_storage_key(storage_key: str) -> bool:
    if not storage_key or storage_key != storage_key.strip():
        return False
    if storage_key.startswith("/") or "\\" in storage_key:
        return False
    if "\x00" in storage_key or any(ord(char) < 32 for char in storage_key):
        return False
    return not any(part in {"", ".", ".."} for part in storage_key.split("/"))
