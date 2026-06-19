import zipfile
from io import BytesIO

import pytest
from infinity_context_core.application.asset_upload_policy import (
    UPLOAD_POLICY_VERSION,
    assess_asset_upload,
    detect_magic_content_type,
)
from infinity_context_core.domain.errors import MemoryIngressLimitError


def test_upload_policy_detects_magic_content_types() -> None:
    assert detect_magic_content_type(b"%PDF-1.7\n") == "application/pdf"
    assert detect_magic_content_type(b"\x89PNG\r\n\x1a\npayload") == "image/png"
    assert detect_magic_content_type(b"RIFF\x10\x00\x00\x00WEBPVP8 ") == "image/webp"
    assert detect_magic_content_type(b"RIFF\x24\x00\x00\x00WAVEfmt ") == "audio/wav"
    assert detect_magic_content_type(b"fLaC\x00\x00\x00\x22") == "audio/flac"
    assert detect_magic_content_type(b"OggS\x00\x02audio") == "audio/ogg"
    assert detect_magic_content_type(b"\x00\x00\x00\x18ftypmp42") == "video/mp4"
    assert detect_magic_content_type(b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00") == "audio/mp4"
    assert detect_magic_content_type(b"\x00\x00\x00\x18ftypqt  \x00\x00\x00\x00") == (
        "video/quicktime"
    )
    assert detect_magic_content_type(b"\x00\x00\x00\x18ftypavif\x00\x00\x00\x00") == (
        "image/avif"
    )
    assert detect_magic_content_type(b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00") == (
        "image/heic"
    )
    assert detect_magic_content_type(b"\x1a\x45\xdf\xa3\x00\x00webm") == "video/webm"
    assert detect_magic_content_type(b"plain text body") == "text/plain"


def test_upload_policy_reports_declared_and_extension_mismatch() -> None:
    result = assess_asset_upload(
        filename="screenshot.png",
        declared_content_type="image/png",
        content=b"plain text body",
    )

    assert result.metadata["upload_policy_version"] == UPLOAD_POLICY_VERSION
    assert result.metadata["upload_extension_content_type"] == "image/png"
    assert result.metadata["upload_magic_content_type"] == "text/plain"
    assert result.metadata["upload_content_type_mismatch"] is True
    assert result.metadata["upload_extension_mismatch"] is True


def test_upload_policy_marks_non_document_zip_archive_for_review() -> None:
    result = assess_asset_upload(
        filename="payload.zip",
        declared_content_type="application/zip",
        content=_zip_bytes({"notes.txt": b"hello"}),
    )

    assert result.metadata["upload_magic_content_type"] == "application/zip"
    assert result.metadata["upload_archive_detected"] is True
    assert result.metadata["upload_archive_review_required"] is True
    assert result.metadata["upload_archive_review_reason"] == "zip_archive_not_structured_document"
    assert result.metadata["upload_archive_inspection_status"] == "ok"
    assert result.metadata["upload_archive_entry_count"] == 1
    assert result.metadata["upload_archive_uncompressed_bytes"] == 5


def test_upload_policy_keeps_office_zip_container_without_archive_review() -> None:
    result = assess_asset_upload(
        filename="meeting-notes.docx",
        declared_content_type="application/octet-stream",
        content=_zip_bytes({"[Content_Types].xml": b"<Types />", "word/document.xml": b"<w />"}),
    )

    assert result.metadata["upload_magic_content_type"] == "application/zip"
    assert result.metadata["upload_archive_detected"] is True
    assert result.metadata["upload_archive_review_required"] is False
    assert result.metadata["upload_archive_inspection_status"] == "ok"


def test_upload_policy_marks_invalid_zip_for_review_without_crashing() -> None:
    result = assess_asset_upload(
        filename="meeting-notes.docx",
        declared_content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        content=b"PK\x03\x04not actually a valid zip central directory",
    )

    assert result.metadata["upload_archive_detected"] is True
    assert result.metadata["upload_archive_inspection_status"] == "invalid"
    assert result.metadata["upload_archive_review_required"] is True
    assert result.metadata["upload_archive_review_reason"] == "zip_archive_invalid"


def test_upload_policy_rejects_archive_path_traversal() -> None:
    with pytest.raises(MemoryIngressLimitError, match="unsafe paths"):
        assess_asset_upload(
            filename="payload.zip",
            declared_content_type="application/zip",
            content=_zip_bytes({"../escape.txt": b"nope"}),
        )


def test_upload_policy_rejects_archive_compression_bomb_ratio() -> None:
    with pytest.raises(MemoryIngressLimitError, match="compression ratio"):
        assess_asset_upload(
            filename="payload.zip",
            declared_content_type="application/zip",
            content=_zip_bytes({"huge.txt": b"0" * (2 * 1024 * 1024)}),
            max_archive_compression_ratio=10,
        )


def test_upload_policy_rejects_archive_uncompressed_size_limit() -> None:
    with pytest.raises(MemoryIngressLimitError, match="uncompressed size"):
        assess_asset_upload(
            filename="payload.zip",
            declared_content_type="application/zip",
            content=_zip_bytes({"huge.txt": b"x" * 1024}),
            max_archive_uncompressed_bytes=512,
        )


def test_upload_policy_marks_duplicate_archive_paths_for_review() -> None:
    result = assess_asset_upload(
        filename="payload.zip",
        declared_content_type="application/zip",
        content=_zip_bytes(
            {
                "notes/summary.txt": b"first",
                "notes\\SUMMARY.txt": b"second",
            }
        ),
    )

    assert result.metadata["upload_archive_review_required"] is True
    assert result.metadata["upload_archive_review_reason"] == "zip_archive_contains_duplicate_paths"
    assert result.metadata["upload_archive_duplicate_path_count"] == 1


@pytest.mark.parametrize("filename", ["../secret.txt", "nested/secret.txt", "run.exe"])
def test_upload_policy_blocks_dangerous_filenames(filename: str) -> None:
    with pytest.raises(MemoryIngressLimitError):
        assess_asset_upload(
            filename=filename,
            declared_content_type="text/plain",
            content=b"hello",
        )


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()
