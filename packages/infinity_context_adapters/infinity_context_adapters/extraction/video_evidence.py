"""Video keyframe evidence helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass

from infinity_context_core.ports.extraction import (
    ExtractedElement,
    ExtractionArtifactCandidate,
)

from infinity_context_adapters.extraction.image_evidence import (
    extract_tesseract_ocr_blocks,
    full_image_region,
    read_image_metadata,
)
from infinity_context_adapters.extraction.media_tools import VideoKeyframe


@dataclass(frozen=True)
class VideoFrameEvidence:
    elements: tuple[ExtractedElement, ...]
    timeline_artifact: ExtractionArtifactCandidate
    metadata: dict[str, object]


def analyze_video_keyframes(
    *,
    frames: tuple[VideoKeyframe, ...],
    parser_name: str,
    enable_ocr: bool,
    ocr_timeout_seconds: float,
) -> VideoFrameEvidence:
    elements: list[ExtractedElement] = []
    frame_payloads: list[dict[str, object]] = []
    ocr_extracted_count = 0
    for frame in frames:
        image = read_image_metadata(frame.content)
        frame_metadata = {
            **frame.metadata,
            "filename": frame.filename,
            "content_type": frame.content_type,
            "time_start_ms": frame.time_start_ms,
            "time_end_ms": _frame_time_end_ms(frame),
        }
        if image is not None:
            frame_metadata.update(image.as_metadata())
            elements.append(
                full_image_region(
                    metadata=image,
                    parser_name=parser_name,
                    kind="video_keyframe",
                    text=(
                        f"Video keyframe {frame.filename} at "
                        f"{frame.time_start_ms}ms"
                    ),
                ).to_element(parser_name=parser_name)
            )
            elements[-1] = _with_frame_time(elements[-1], frame=frame)
        ocr_status = "disabled"
        ocr_text_preview = ""
        ocr_block_count = 0
        if enable_ocr:
            ocr = extract_tesseract_ocr_blocks(
                content=frame.content,
                extension="jpg",
                timeout_seconds=int(max(1, ocr_timeout_seconds)),
            )
            ocr_status = ocr.status
            ocr_block_count = len(ocr.regions)
            ocr_text_preview = ocr.text[:240]
            if ocr.text.strip():
                ocr_extracted_count += 1
            for region in ocr.regions:
                element = region.to_element(parser_name=parser_name)
                elements.append(_with_frame_time(element, frame=frame))
        frame_payloads.append(
            {
                **frame_metadata,
                "ocr_status": ocr_status,
                "ocr_block_count": ocr_block_count,
                "ocr_text_preview": ocr_text_preview,
            }
        )

    payload = {
        "schema_name": "infinity_context.video_frame_timeline",
        "schema_version": 1,
        "parser": parser_name,
        "frames": frame_payloads,
    }
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    timeline_artifact = ExtractionArtifactCandidate(
        artifact_type="video_frame_timeline",
        filename="video-frame-timeline.json",
        content_type="application/json",
        content=content,
        metadata={
            "parser": parser_name,
            "frame_count": len(frames),
            "ocr_extracted_frame_count": ocr_extracted_count,
        },
    )
    return VideoFrameEvidence(
        elements=tuple(elements),
        timeline_artifact=timeline_artifact,
        metadata={
            "video_keyframe_count": len(frames),
            "video_keyframe_ocr_extracted_count": ocr_extracted_count,
        },
    )


def _with_frame_time(element: ExtractedElement, *, frame: VideoKeyframe) -> ExtractedElement:
    return ExtractedElement(
        kind=element.kind,
        text=element.text,
        page_number=element.page_number,
        time_start_ms=frame.time_start_ms,
        time_end_ms=_frame_time_end_ms(frame),
        bbox=element.bbox,
        confidence=element.confidence,
        metadata=element.metadata,
    )


def _frame_time_end_ms(frame: VideoKeyframe) -> int:
    return frame.time_end_ms if frame.time_end_ms is not None else frame.time_start_ms
