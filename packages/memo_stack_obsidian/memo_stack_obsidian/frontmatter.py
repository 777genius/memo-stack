"""Small frontmatter reader/writer for connector-owned scalar metadata."""

from __future__ import annotations

from collections.abc import Mapping


class FrontmatterError(ValueError):
    pass


def split_frontmatter(markdown: str) -> tuple[dict[str, object], str]:
    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        return {}, normalized
    closing = normalized.find("\n---\n", 4)
    if closing == -1:
        raise FrontmatterError("Frontmatter is not closed")
    header = normalized[4:closing]
    body = normalized[closing + len("\n---\n") :]
    return parse_scalar_frontmatter(header), body


def parse_scalar_frontmatter(header: str) -> dict[str, object]:
    data: dict[str, object] = {}
    for line_number, raw_line in enumerate(header.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise FrontmatterError(f"Invalid frontmatter line {line_number}")
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if not key:
            raise FrontmatterError(f"Invalid empty frontmatter key on line {line_number}")
        data[key] = _parse_scalar(raw_value.strip())
    return data


def dump_frontmatter(data: Mapping[str, object]) -> str:
    lines = ["---"]
    for key, value in data.items():
        lines.append(f"{key}: {_format_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _parse_scalar(value: str) -> object:
    if value == "":
        return ""
    if value in {"true", "false"}:
        return value == "true"
    if value.isdigit():
        return int(value)
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _format_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if not text or any(char in text for char in ":#\n\r"):
        return repr(text)
    return text
