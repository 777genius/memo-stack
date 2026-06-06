"""Redact local agent transcripts into benchmark corpus fixtures.

The tool is intentionally conservative: it reads only explicit files or a
non-recursive directory by default, redacts common secret/path/email patterns,
and writes JSON fixtures compatible with MEMORY_AGENT_BENCH_TRANSCRIPT_CORPUS_DIR.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SUPPORTED_SUFFIXES = {".json", ".jsonl", ".txt", ".md"}
DEFAULT_MAX_FILES = 50
DEFAULT_MAX_BYTES = 300_000
DEFAULT_MAX_TRANSCRIPT_CHARS = 120_000
IMPORTER_VERSION = "agent-transcript-corpus-redactor-v1"

REDACTION_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "bearer_token",
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
        "Bearer <redacted:token>",
    ),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "<redacted:secret>"),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{12,}\b"), "<redacted:secret>"),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{12,}\b"), "<redacted:secret>"),
    (
        "assignment_secret",
        re.compile(
            r"(?i)\b(api[_-]?key|secret|token|password|passwd|credential)\s*[:=]\s*['\"]?"
            r"[A-Za-z0-9_./+=-]{8,}"
        ),
        r"\1=<redacted:secret>",
    ),
    (
        "email",
        re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
        "<redacted:email>",
    ),
    (
        "home_path",
        re.compile(r"(?<![A-Za-z0-9_])/(Users|home)/[A-Za-z0-9._-]+/[^\s\"']*"),
        r"/\1/<redacted:path>",
    ),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Transcript file or directory")
    parser.add_argument("output_dir", type=Path, help="Directory for redacted corpus JSON")
    parser.add_argument("--recursive", action="store_true", help="Read directories recursively")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--max-transcript-chars", type=int, default=DEFAULT_MAX_TRANSCRIPT_CHARS)
    parser.add_argument("--tag", action="append", default=[], help="Extra tag for every fixture")
    args = parser.parse_args(argv)

    try:
        result = redact_transcript_corpus(
            input_path=args.input,
            output_dir=args.output_dir,
            recursive=args.recursive,
            max_files=args.max_files,
            max_bytes=args.max_bytes,
            max_transcript_chars=args.max_transcript_chars,
            extra_tags=tuple(args.tag),
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


def redact_transcript_corpus(
    *,
    input_path: Path,
    output_dir: Path,
    recursive: bool = False,
    max_files: int = DEFAULT_MAX_FILES,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_transcript_chars: int = DEFAULT_MAX_TRANSCRIPT_CHARS,
    extra_tags: tuple[str, ...] = (),
) -> dict[str, Any]:
    if max_files <= 0:
        raise ValueError("max_files must be positive")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if max_transcript_chars <= 0:
        raise ValueError("max_transcript_chars must be positive")

    paths = _input_paths(input_path, recursive=recursive, max_files=max_files)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    skipped: list[dict[str, str]] = []
    total_counts: Counter[str] = Counter()
    for path in paths:
        if path.stat().st_size > max_bytes:
            skipped.append({"file": path.name, "reason": "file_too_large"})
            continue
        raw_bytes = path.read_bytes()
        source_hash = hashlib.sha256(raw_bytes).hexdigest()
        raw_text = raw_bytes.decode("utf-8", errors="replace")
        transcript = _extract_transcript(path, raw_text)
        if not transcript.strip():
            skipped.append({"file": path.name, "reason": "empty_transcript"})
            continue
        redacted, counts = redact_text(transcript)
        total_counts.update(counts)
        fixture = _fixture(
            source_hash=source_hash,
            source_suffix=path.suffix.lower(),
            redacted_transcript=redacted[:max_transcript_chars],
            truncated=len(redacted) > max_transcript_chars,
            redaction_counts=counts,
            extra_tags=extra_tags,
        )
        output_path = output_dir / f"agent-transcript-{source_hash[:16]}.json"
        output_path.write_text(
            json.dumps(fixture, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written.append(output_path.name)
    return {
        "ok": True,
        "written_count": len(written),
        "written_files": written,
        "skipped": skipped,
        "redaction_counts": dict(sorted(total_counts.items())),
    }


def redact_text(text: str) -> tuple[str, dict[str, int]]:
    counts: Counter[str] = Counter()
    redacted = text
    for name, pattern, replacement in REDACTION_RULES:
        redacted, count = pattern.subn(replacement, redacted)
        if count:
            counts[name] += count
    return redacted, dict(sorted(counts.items()))


def _input_paths(input_path: Path, *, recursive: bool, max_files: int) -> list[Path]:
    path = input_path.expanduser()
    if path.is_file():
        paths = [path]
    elif path.is_dir():
        iterator = path.rglob("*") if recursive else path.iterdir()
        paths = sorted(
            item
            for item in iterator
            if item.is_file() and item.suffix.lower() in SUPPORTED_SUFFIXES
        )
    else:
        raise ValueError("input path must be a file or directory")
    return paths[:max_files]


def _extract_transcript(path: Path, raw_text: str) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _transcript_from_payload(json.loads(raw_text))
    if suffix == ".jsonl":
        return _render_turns(json.loads(line) for line in raw_text.splitlines() if line.strip())
    return raw_text


def _transcript_from_payload(payload: object) -> str:
    if isinstance(payload, dict):
        for key in ("transcript", "text", "content"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
        for key in ("turns", "messages", "events", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return _render_turns(value)
    if isinstance(payload, list):
        return _render_turns(payload)
    return ""


def _render_turns(turns: Any) -> str:
    lines: list[str] = []
    for turn in turns:
        if isinstance(turn, dict):
            role = str(turn.get("role") or turn.get("speaker") or turn.get("type") or "unknown")
            text = _turn_text(turn)
            if text:
                lines.append(f"{role}: {text}")
        elif isinstance(turn, str) and turn.strip():
            lines.append(turn.strip())
    return "\n".join(lines)


def _turn_text(turn: dict[str, Any]) -> str:
    for key in ("content", "text", "message", "output"):
        value = turn.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            joined = " ".join(_content_part_text(part) for part in value)
            if joined.strip():
                return joined.strip()
    return ""


def _content_part_text(part: object) -> str:
    if isinstance(part, str):
        return part
    if isinstance(part, dict):
        value = part.get("text") or part.get("content")
        return value if isinstance(value, str) else ""
    return ""


def _fixture(
    *,
    source_hash: str,
    source_suffix: str,
    redacted_transcript: str,
    truncated: bool,
    redaction_counts: dict[str, int],
    extra_tags: tuple[str, ...],
) -> dict[str, Any]:
    forbidden = sorted(
        {
            marker
            for marker in (
                "<redacted:email>",
                "<redacted:path>",
                "<redacted:secret>",
                "<redacted:token>",
            )
            if marker in redacted_transcript
        }
    )
    return {
        "id": f"imported-{source_hash[:16]}",
        "title": f"Imported agent transcript {source_hash[:8]}",
        "category": "document",
        "transcript": redacted_transcript,
        "expected_tools": ["memory_search", "memory_ingest_document"],
        "forbidden_contains": forbidden,
        "tags": ["imported_real_transcript", *extra_tags],
        "metadata": {
            "importer_version": IMPORTER_VERSION,
            "source_sha256": source_hash,
            "source_suffix": source_suffix,
            "redaction_counts": redaction_counts,
            "truncated": truncated,
            "manual_annotation_recommended": True,
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
