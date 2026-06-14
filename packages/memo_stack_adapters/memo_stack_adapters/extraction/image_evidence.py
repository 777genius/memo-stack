"""Image evidence normalization helpers for OCR and vision adapters."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from io import BytesIO, StringIO
from typing import Any

from memo_stack_core.ports.extraction import (
    ExtractedElement,
    ExtractionArtifactCandidate,
)

_MAX_OCR_BLOCKS = 500


@dataclass(frozen=True)
class ImageMetadata:
    width: int
    height: int
    image_format: str | None
    mode: str | None

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (0.0, 0.0, float(self.width), float(self.height))

    def as_metadata(self) -> dict[str, object]:
        return {
            "image_width": self.width,
            "image_height": self.height,
            "image_format": self.image_format,
            "image_mode": self.mode,
        }


@dataclass(frozen=True)
class ImageRegion:
    kind: str
    text: str
    bbox: tuple[float, float, float, float] | None
    confidence: float | None = None
    metadata: dict[str, object] | None = None

    def to_element(self, *, parser_name: str) -> ExtractedElement:
        return ExtractedElement(
            kind=self.kind,
            text=self.text,
            bbox=self.bbox,
            confidence=self.confidence,
            metadata={"source": parser_name, **(self.metadata or {})},
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "text": self.text,
            "bbox": list(self.bbox) if self.bbox is not None else None,
            "confidence": self.confidence,
            "metadata": self.metadata or {},
        }


@dataclass(frozen=True)
class OcrExtractionResult:
    text: str
    status: str
    regions: tuple[ImageRegion, ...] = ()


def read_image_metadata(content: bytes) -> ImageMetadata | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(BytesIO(content)) as image:
            image.load()
            width, height = image.size
            return ImageMetadata(
                width=width,
                height=height,
                image_format=image.format,
                mode=image.mode,
            )
    except Exception:
        return None


def full_image_region(
    *,
    metadata: ImageMetadata,
    text: str,
    parser_name: str,
    kind: str = "image_metadata",
) -> ImageRegion:
    return ImageRegion(
        kind=kind,
        text=text,
        bbox=metadata.bbox,
        metadata={"source": parser_name, **metadata.as_metadata()},
    )


def image_regions_artifact(
    *,
    filename: str,
    parser_name: str,
    image: ImageMetadata,
    regions: tuple[ImageRegion, ...],
    metadata: dict[str, object] | None = None,
) -> ExtractionArtifactCandidate:
    payload = {
        "schema_name": "memo_stack.image_regions",
        "schema_version": "1.0",
        "parser": parser_name,
        "image": image.as_metadata(),
        "regions": [region.to_payload() for region in regions],
        "region_count": len(regions),
        "metadata": metadata or {},
    }
    return json_artifact(
        artifact_type="image_regions",
        filename=filename,
        payload=payload,
        parser_name=parser_name,
        metadata={
            "region_count": len(regions),
            **(metadata or {}),
        },
    )


def json_artifact(
    *,
    artifact_type: str,
    filename: str,
    payload: dict[str, object],
    parser_name: str,
    metadata: dict[str, object] | None = None,
) -> ExtractionArtifactCandidate:
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return ExtractionArtifactCandidate(
        artifact_type=artifact_type,
        filename=filename,
        content_type="application/json",
        content=content,
        metadata={"parser": parser_name, **(metadata or {})},
    )


def extract_tesseract_ocr_blocks(
    *,
    content: bytes,
    extension: str | None,
    timeout_seconds: int = 20,
) -> OcrExtractionResult:
    tesseract = shutil.which("tesseract")
    if not tesseract:
        return OcrExtractionResult(text="", status="unavailable")
    suffix = f".{extension}" if extension else ".img"
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix) as image_file:
            image_file.write(content)
            image_file.flush()
            completed = subprocess.run(
                [tesseract, image_file.name, "stdout", "tsv"],
                check=False,
                capture_output=True,
                timeout=timeout_seconds,
            )
    except (OSError, subprocess.TimeoutExpired):
        return OcrExtractionResult(text="", status="failed")
    if completed.returncode != 0:
        return OcrExtractionResult(text="", status="failed")
    tsv = completed.stdout.decode("utf-8", errors="replace").strip()
    regions = parse_tesseract_tsv(tsv)
    text = "\n".join(region.text for region in regions if region.text.strip())
    return OcrExtractionResult(
        text=text,
        status="extracted" if text.strip() else "no_text",
        regions=tuple(regions),
    )


def parse_tesseract_tsv(tsv: str) -> tuple[ImageRegion, ...]:
    if not tsv.strip():
        return ()
    reader = csv.DictReader(StringIO(tsv), delimiter="\t")
    line_words: dict[tuple[str, str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in reader:
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        confidence = _float(row.get("conf"))
        if confidence is not None and confidence < 0:
            continue
        bbox = _bbox_from_tesseract_row(row)
        if bbox is None:
            continue
        key = (
            str(row.get("page_num") or "1"),
            str(row.get("block_num") or "0"),
            str(row.get("par_num") or "0"),
            str(row.get("line_num") or "0"),
        )
        line_words[key].append(
            {
                "text": text,
                "bbox": bbox,
                "confidence": confidence,
                "word_num": _int(row.get("word_num")) or len(line_words[key]) + 1,
            }
        )
    regions: list[ImageRegion] = []
    for key in sorted(line_words, key=_line_sort_key):
        words = sorted(line_words[key], key=lambda item: int(item["word_num"]))
        line_text = " ".join(str(word["text"]) for word in words).strip()
        if not line_text:
            continue
        confidences = [
            float(word["confidence"])
            for word in words
            if isinstance(word.get("confidence"), (int, float))
        ]
        regions.append(
            ImageRegion(
                kind="ocr_text",
                text=line_text,
                bbox=_union_bbox(tuple(word["bbox"] for word in words)),
                confidence=(
                    round(sum(confidences) / len(confidences) / 100.0, 4) if confidences else None
                ),
                metadata={
                    "source": "tesseract_cli",
                    "ocr_page": key[0],
                    "ocr_block": key[1],
                    "ocr_paragraph": key[2],
                    "ocr_line": key[3],
                    "ocr_word_count": len(words),
                },
            )
        )
        if len(regions) >= _MAX_OCR_BLOCKS:
            break
    return tuple(regions)


def normalize_bbox(value: Any) -> tuple[float, float, float, float] | None:
    if isinstance(value, dict):
        candidates = (
            (value.get("x"), value.get("y"), value.get("width"), value.get("height")),
            (value.get("left"), value.get("top"), value.get("right"), value.get("bottom")),
            (value.get("x0"), value.get("y0"), value.get("x1"), value.get("y1")),
        )
        for candidate in candidates:
            numbers = tuple(_float(item) for item in candidate)
            if all(item is not None for item in numbers):
                if "width" in value or "height" in value:
                    x, y, width, height = numbers
                    return (x, y, x + width, y + height)  # type: ignore[operator]
                return numbers  # type: ignore[return-value]
    if isinstance(value, (list, tuple)) and len(value) == 4:
        numbers = tuple(_float(item) for item in value)
        if all(item is not None for item in numbers):
            return numbers  # type: ignore[return-value]
    return None


def _bbox_from_tesseract_row(
    row: dict[str, str | None],
) -> tuple[float, float, float, float] | None:
    left = _float(row.get("left"))
    top = _float(row.get("top"))
    width = _float(row.get("width"))
    height = _float(row.get("height"))
    if left is None or top is None or width is None or height is None:
        return None
    return (left, top, left + width, top + height)


def _union_bbox(values: tuple[object, ...]) -> tuple[float, float, float, float] | None:
    boxes = [box for box in values if isinstance(box, tuple) and len(box) == 4]
    if not boxes:
        return None
    return (
        min(float(box[0]) for box in boxes),
        min(float(box[1]) for box in boxes),
        max(float(box[2]) for box in boxes),
        max(float(box[3]) for box in boxes),
    )


def _line_sort_key(key: tuple[str, str, str, str]) -> tuple[int, int, int, int]:
    return tuple(_int(item) or 0 for item in key)


def _int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None
