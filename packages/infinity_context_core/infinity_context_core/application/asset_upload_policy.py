"""Provider-neutral asset upload security policy."""

from __future__ import annotations

import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath, PureWindowsPath

from infinity_context_core.application.safe_payload import safe_metadata_text
from infinity_context_core.domain.errors import MemoryIngressLimitError

UPLOAD_POLICY_VERSION = "asset-upload-policy-v1"
_MAX_FILENAME_CHARS = 240
_MAX_CONTENT_TYPE_CHARS = 120
_MAX_ARCHIVE_ENTRIES = 2_000
_MAX_ARCHIVE_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
_MAX_ARCHIVE_SINGLE_ENTRY_BYTES = 100 * 1024 * 1024
_MAX_ARCHIVE_COMPRESSION_RATIO = 100.0
_ARCHIVE_RATIO_MIN_UNCOMPRESSED_BYTES = 1 * 1024 * 1024
_BLOCKED_EXTENSIONS = {
    ".app",
    ".bat",
    ".cmd",
    ".com",
    ".dmg",
    ".dll",
    ".exe",
    ".msi",
    ".ps1",
    ".scr",
    ".sh",
}
_NESTED_ARCHIVE_EXTENSIONS = {
    ".7z",
    ".bz2",
    ".gz",
    ".rar",
    ".tar",
    ".tgz",
    ".xz",
    ".zip",
}
_EXTENSION_CONTENT_TYPES = {
    ".csv": "text/csv",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".gif": "image/gif",
    ".html": "text/html",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".json": "application/json",
    ".m4a": "audio/mp4",
    ".md": "text/markdown",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".mpeg": "video/mpeg",
    ".mpga": "audio/mpeg",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".wav": "audio/wav",
    ".webm": "video/webm",
    ".webp": "image/webp",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xml": "application/xml",
    ".zip": "application/zip",
}
_TEXT_BYTES = set(range(32, 127)) | {9, 10, 13}


@dataclass(frozen=True)
class AssetUploadAssessment:
    declared_content_type: str
    extension_content_type: str | None
    magic_content_type: str
    metadata: dict[str, object]


def assess_asset_upload(
    *,
    filename: str,
    declared_content_type: str,
    content: bytes,
    max_archive_entries: int = _MAX_ARCHIVE_ENTRIES,
    max_archive_uncompressed_bytes: int = _MAX_ARCHIVE_UNCOMPRESSED_BYTES,
    max_archive_single_entry_bytes: int = _MAX_ARCHIVE_SINGLE_ENTRY_BYTES,
    max_archive_compression_ratio: float = _MAX_ARCHIVE_COMPRESSION_RATIO,
) -> AssetUploadAssessment:
    safe_filename = safe_metadata_text(filename.strip(), limit=_MAX_FILENAME_CHARS)
    if not safe_filename:
        raise MemoryIngressLimitError("Asset filename is required")
    if "\x00" in filename or any(ord(char) < 32 for char in filename):
        raise MemoryIngressLimitError("Asset filename contains control characters")
    if _looks_like_path(filename):
        raise MemoryIngressLimitError("Asset filename must not contain path separators")
    extension = _extension(safe_filename)
    if extension in _BLOCKED_EXTENSIONS:
        raise MemoryIngressLimitError("Asset filename extension is blocked")

    declared = _normalize_content_type(declared_content_type)
    extension_content_type = _EXTENSION_CONTENT_TYPES.get(extension)
    magic_content_type = detect_magic_content_type(content)
    extension_mismatch = bool(
        extension_content_type
        and magic_content_type != "application/octet-stream"
        and not _content_types_compatible(extension_content_type, magic_content_type)
    )
    declared_mismatch = bool(
        declared
        and magic_content_type != "application/octet-stream"
        and not _content_types_compatible(declared, magic_content_type)
    )
    archive_detected = magic_content_type == "application/zip"
    archive_review_required = archive_detected and not (
        _is_structured_document_content_type(declared)
        or _is_structured_document_content_type(extension_content_type)
    )
    archive_metadata: dict[str, object] = {}
    if archive_detected:
        archive_metadata = _inspect_zip_archive(
            content,
            max_entries=max_archive_entries,
            max_uncompressed_bytes=max_archive_uncompressed_bytes,
            max_single_entry_bytes=max_archive_single_entry_bytes,
            max_compression_ratio=max_archive_compression_ratio,
        )
        archive_review_required = archive_review_required or bool(
            archive_metadata.get("upload_archive_review_required")
        )
    metadata = {
        "upload_policy_version": UPLOAD_POLICY_VERSION,
        "upload_declared_content_type": declared or "application/octet-stream",
        "upload_extension": extension or None,
        "upload_extension_content_type": extension_content_type,
        "upload_magic_content_type": magic_content_type,
        "upload_content_type_mismatch": declared_mismatch,
        "upload_extension_mismatch": extension_mismatch,
        "upload_archive_detected": archive_detected,
        "upload_archive_review_required": archive_review_required,
        "upload_dangerous_extension_blocked": False,
        **archive_metadata,
    }
    metadata["upload_archive_review_reason"] = _archive_review_reason(
        raw_archive_review_required=archive_detected
        and not (
            _is_structured_document_content_type(declared)
            or _is_structured_document_content_type(extension_content_type)
        ),
        archive_metadata=archive_metadata,
    )
    return AssetUploadAssessment(
        declared_content_type=declared or "application/octet-stream",
        extension_content_type=extension_content_type,
        magic_content_type=magic_content_type,
        metadata=metadata,
    )


def detect_magic_content_type(content: bytes) -> str:
    head = content[:512]
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return "audio/wav"
    if head.startswith(b"ID3") or _looks_like_mp3_frame(head):
        return "audio/mpeg"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return "video/mp4"
    if head.startswith(b"PK\x03\x04"):
        return "application/zip"
    if head[:16].lstrip().startswith((b"{", b"[")):
        return "application/json"
    if _looks_like_text(head):
        return "text/plain"
    return "application/octet-stream"


def _inspect_zip_archive(
    content: bytes,
    *,
    max_entries: int,
    max_uncompressed_bytes: int,
    max_single_entry_bytes: int,
    max_compression_ratio: float,
) -> dict[str, object]:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
    except (zipfile.BadZipFile, RuntimeError, OSError):
        return {
            "upload_archive_inspection_status": "invalid",
            "upload_archive_review_required": True,
            "upload_archive_review_reason": "zip_archive_invalid",
        }

    entry_count = len(entries)
    file_entries = [entry for entry in entries if not entry.is_dir()]
    total_uncompressed = sum(max(0, int(entry.file_size)) for entry in file_entries)
    total_compressed = sum(max(0, int(entry.compress_size)) for entry in file_entries)
    max_entry_size = max((max(0, int(entry.file_size)) for entry in file_entries), default=0)
    max_ratio = _max_archive_compression_ratio(file_entries)
    dangerous_paths = tuple(
        entry.filename for entry in entries if _archive_path_is_unsafe(entry.filename)
    )
    nested_entries = tuple(
        entry.filename
        for entry in file_entries
        if _extension(entry.filename) in _NESTED_ARCHIVE_EXTENSIONS
    )
    encrypted_count = sum(1 for entry in file_entries if entry.flag_bits & 0x1)
    metadata = {
        "upload_archive_inspection_status": "ok",
        "upload_archive_entry_count": entry_count,
        "upload_archive_file_count": len(file_entries),
        "upload_archive_directory_count": entry_count - len(file_entries),
        "upload_archive_uncompressed_bytes": total_uncompressed,
        "upload_archive_compressed_bytes": total_compressed,
        "upload_archive_max_entry_uncompressed_bytes": max_entry_size,
        "upload_archive_max_compression_ratio": round(max_ratio, 3),
        "upload_archive_encrypted_entry_count": encrypted_count,
        "upload_archive_nested_archive_count": len(nested_entries),
        "upload_archive_unsafe_path_count": len(dangerous_paths),
        "upload_archive_limits": {
            "max_entries": max_entries,
            "max_uncompressed_bytes": max_uncompressed_bytes,
            "max_single_entry_bytes": max_single_entry_bytes,
            "max_compression_ratio": max_compression_ratio,
        },
    }
    if dangerous_paths:
        raise MemoryIngressLimitError("Asset archive contains unsafe paths")
    if entry_count > max_entries:
        raise MemoryIngressLimitError("Asset archive exceeds configured entry limit")
    if max_entry_size > max_single_entry_bytes:
        raise MemoryIngressLimitError("Asset archive entry exceeds configured size limit")
    if total_uncompressed > max_uncompressed_bytes:
        raise MemoryIngressLimitError("Asset archive uncompressed size exceeds configured limit")
    if (
        max_ratio > max_compression_ratio
        and total_uncompressed >= _ARCHIVE_RATIO_MIN_UNCOMPRESSED_BYTES
    ):
        raise MemoryIngressLimitError("Asset archive compression ratio exceeds configured limit")
    if nested_entries or encrypted_count:
        metadata["upload_archive_review_required"] = True
        metadata["upload_archive_review_reason"] = (
            "zip_archive_contains_encrypted_entries"
            if encrypted_count
            else "zip_archive_contains_nested_archives"
        )
    return metadata


def _looks_like_path(filename: str) -> bool:
    if "/" in filename or "\\" in filename:
        return True
    if PurePosixPath(filename).name != filename:
        return True
    return PureWindowsPath(filename).name != filename


def _extension(filename: str) -> str:
    name = filename.rsplit(".", 1)
    return f".{name[1].lower()}" if len(name) == 2 and name[1] else ""


def _archive_path_is_unsafe(filename: str) -> bool:
    if "\x00" in filename:
        return True
    windows_path = PureWindowsPath(filename)
    if windows_path.drive or windows_path.is_absolute():
        return True
    normalized = filename.replace("\\", "/")
    if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
        return True
    parts = PurePosixPath(normalized).parts
    return any(part in {"", ".", ".."} for part in parts)


def _max_archive_compression_ratio(entries: Iterable[zipfile.ZipInfo]) -> float:
    max_ratio = 0.0
    for entry in entries:
        file_size = max(0, int(entry.file_size))
        compressed_size = max(0, int(entry.compress_size))
        if file_size <= 0:
            continue
        ratio = float("inf") if compressed_size <= 0 else file_size / compressed_size
        max_ratio = max(max_ratio, ratio)
    return max_ratio


def _archive_review_reason(
    *,
    raw_archive_review_required: bool,
    archive_metadata: dict[str, object],
) -> str | None:
    if reason := archive_metadata.get("upload_archive_review_reason"):
        return str(reason)
    return "zip_archive_not_structured_document" if raw_archive_review_required else None


def _normalize_content_type(value: str) -> str:
    normalized = value.split(";", 1)[0].strip().lower()
    return safe_metadata_text(normalized, limit=_MAX_CONTENT_TYPE_CHARS)


def _content_types_compatible(expected: str, actual: str) -> bool:
    expected = _normalize_content_type(expected)
    actual = _normalize_content_type(actual)
    if expected == actual:
        return True
    pairs = {
        ("audio/mp4", "video/mp4"),
        ("video/mp4", "audio/mp4"),
        ("application/json", "text/plain"),
        ("text/plain", "application/json"),
    }
    if (expected, actual) in pairs:
        return True
    if expected.startswith("text/") and actual == "text/plain":
        return True
    return _is_structured_document_content_type(expected) and actual == "application/zip"


def _is_structured_document_content_type(value: str | None) -> bool:
    return value in _STRUCTURED_DOCUMENT_CONTAINER_TYPES


def _looks_like_mp3_frame(head: bytes) -> bool:
    return len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0


def _looks_like_text(head: bytes) -> bool:
    if not head:
        return False
    sample = head[:256]
    if b"\x00" in sample:
        return False
    printable = sum(1 for byte in sample if byte in _TEXT_BYTES)
    return printable / len(sample) >= 0.85


_STRUCTURED_DOCUMENT_CONTAINER_TYPES = {
    "application/epub+zip",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "message/rfc822",
}
