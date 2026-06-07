"""Vault folder layout policy for the Obsidian connector."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath

from memo_stack_obsidian.domain import content_hash

DEFAULT_ROOT_FOLDER = "Memo Stack"
LEGACY_LAYOUT_VERSION = "v1"
DEFAULT_LAYOUT_VERSION = "v2"


class LayoutError(ValueError):
    pass


class LayoutVersion(StrEnum):
    V1 = LEGACY_LAYOUT_VERSION
    V2 = DEFAULT_LAYOUT_VERSION


@dataclass(frozen=True)
class ObsidianVaultLayout:
    root_folder: PurePosixPath = PurePosixPath(DEFAULT_ROOT_FOLDER)
    version: LayoutVersion = LayoutVersion.V1
    include_legacy_scan: bool = True

    @classmethod
    def from_values(
        cls,
        *,
        root_folder: str | PurePosixPath = DEFAULT_ROOT_FOLDER,
        version: str | LayoutVersion = LayoutVersion.V2,
        include_legacy_scan: bool = True,
    ) -> ObsidianVaultLayout:
        return cls(
            root_folder=safe_root_folder(root_folder),
            version=LayoutVersion(str(version)),
            include_legacy_scan=include_legacy_scan,
        )

    def root_dir(self) -> PurePosixPath:
        return self.root_folder

    def facts_dir(self, *, space_slug: str, profile_external_ref: str) -> PurePosixPath:
        if self.version == LayoutVersion.V1:
            return self.root_folder / "generated" / "facts"
        return self._scope_dir(
            space_slug=space_slug,
            profile_external_ref=profile_external_ref,
        ) / "generated" / "facts"

    def inbox_dir(self, *, space_slug: str, profile_external_ref: str) -> PurePosixPath:
        if self.version == LayoutVersion.V1:
            return self.root_folder / "inbox"
        return self._scope_dir(
            space_slug=space_slug,
            profile_external_ref=profile_external_ref,
        ) / "inbox"

    def conflicts_dir(self, *, space_slug: str, profile_external_ref: str) -> PurePosixPath:
        if self.version == LayoutVersion.V1:
            return self.root_folder / "conflicts"
        return self._scope_dir(
            space_slug=space_slug,
            profile_external_ref=profile_external_ref,
        ) / "conflicts"

    def fact_note_path(
        self,
        fact_id: str,
        *,
        space_slug: str,
        profile_external_ref: str,
    ) -> PurePosixPath:
        return self.facts_dir(
            space_slug=space_slug,
            profile_external_ref=profile_external_ref,
        ) / f"{safe_filename(fact_id)}.md"

    def fact_scan_dirs(
        self,
        *,
        space_slug: str,
        profile_external_ref: str,
    ) -> tuple[PurePosixPath, ...]:
        current = self.facts_dir(
            space_slug=space_slug,
            profile_external_ref=profile_external_ref,
        )
        legacy = self.root_folder / "generated" / "facts"
        return _unique_paths(
            (current, legacy) if self.include_legacy_scan else (current,)
        )

    def inbox_scan_dirs(
        self,
        *,
        space_slug: str,
        profile_external_ref: str,
    ) -> tuple[PurePosixPath, ...]:
        current = self.inbox_dir(
            space_slug=space_slug,
            profile_external_ref=profile_external_ref,
        )
        legacy = self.root_folder / "inbox"
        return _unique_paths(
            (current, legacy) if self.include_legacy_scan else (current,)
        )

    def _scope_dir(
        self,
        *,
        space_slug: str,
        profile_external_ref: str,
    ) -> PurePosixPath:
        return (
            self.root_folder
            / "spaces"
            / safe_scope_segment(space_slug, "space_slug")
            / "profiles"
            / safe_scope_segment(profile_external_ref, "profile_external_ref")
        )


def safe_root_folder(value: str | PurePosixPath) -> PurePosixPath:
    path = PurePosixPath(str(value).strip())
    if not path.parts:
        raise LayoutError("root_folder cannot be empty")
    if path.is_absolute():
        raise LayoutError("root_folder must be relative to the vault root")
    for part in path.parts:
        if part in {"", ".", ".."}:
            raise LayoutError("root_folder cannot contain empty, dot, or parent segments")
        if _has_control_or_zero_width(part):
            raise LayoutError("root_folder contains unsafe formatting characters")
    return path


def safe_scope_segment(value: str, field_name: str) -> str:
    raw = value.strip()
    if not raw:
        raise LayoutError(f"{field_name} cannot be empty")
    if _has_control_or_zero_width(raw):
        raise LayoutError(f"{field_name} contains unsafe formatting characters")
    normalized = raw.casefold()
    slug = re.sub(r"[^a-z0-9_.-]+", "-", normalized).strip(".-_")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        slug = "scope"
    changed = slug != normalized or len(slug) > 72
    slug = slug[:72].strip(".-_") or "scope"
    if changed:
        slug = f"{slug}--{content_hash(raw)[:8]}"
    return slug


def safe_filename(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return safe.strip("._") or "memo_stack_item"


def _unique_paths(paths: tuple[PurePosixPath, ...]) -> tuple[PurePosixPath, ...]:
    seen: set[str] = set()
    unique: list[PurePosixPath] = []
    for path in paths:
        key = path.as_posix()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return tuple(unique)


def _has_control_or_zero_width(value: str) -> bool:
    return bool(re.search(r"[\x00-\x1f\x7f\u200b-\u200f\ufeff]", value))
