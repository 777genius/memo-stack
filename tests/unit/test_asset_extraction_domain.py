from datetime import UTC, datetime

from memo_stack_core.domain.assets import MemoryAssetId
from memo_stack_core.domain.extraction import (
    AssetExtractionJobId,
    ExtractionArtifact,
    ExtractionArtifactId,
    ExtractionArtifactType,
)


def test_normalized_json_is_a_supported_extraction_artifact_type() -> None:
    artifact = ExtractionArtifact.create(
        artifact_id=ExtractionArtifactId("artifact-normalized"),
        job_id=AssetExtractionJobId("job-docling"),
        asset_id=MemoryAssetId("asset-docling"),
        artifact_type="normalized_json",
        storage_backend="local",
        storage_key="scope/job/docling-normalized.json",
        sha256_hex="a" * 64,
        byte_size=128,
        now=datetime(2026, 6, 14, tzinfo=UTC),
        metadata={"content_type": "application/json"},
    )

    assert artifact.artifact_type == ExtractionArtifactType.NORMALIZED_JSON


def test_image_region_artifacts_are_supported_extraction_artifact_types() -> None:
    assert _artifact("image_regions").artifact_type == ExtractionArtifactType.IMAGE_REGIONS
    assert _artifact("vision_json").artifact_type == ExtractionArtifactType.VISION_JSON


def _artifact(artifact_type: str) -> ExtractionArtifact:
    return ExtractionArtifact.create(
        artifact_id=ExtractionArtifactId(f"artifact-{artifact_type}"),
        job_id=AssetExtractionJobId("job-image"),
        asset_id=MemoryAssetId("asset-image"),
        artifact_type=artifact_type,
        storage_backend="local",
        storage_key=f"scope/job/{artifact_type}.json",
        sha256_hex="b" * 64,
        byte_size=128,
        now=datetime(2026, 6, 14, tzinfo=UTC),
        metadata={"content_type": "application/json"},
    )
