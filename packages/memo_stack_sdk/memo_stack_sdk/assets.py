"""Asset and extraction helpers for the public Memo Stack SDK."""

from __future__ import annotations

from typing import Any

import memo_stack_sdk._payloads as _payloads


class MemoStackAssetsMixin:
    def upload_asset(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str | None = None,
        space_id: str | None = None,
        memory_scope_id: str | None = None,
        thread_id: str | None = None,
        space_slug: str | None = None,
        memory_scope_external_ref: str | None = None,
        thread_external_ref: str | None = None,
        classification: str = "unknown",
        extract: bool = False,
        parser_profile: str | None = None,
    ) -> dict[str, Any]:
        params = _payloads.without_none(
            {
                **_payloads.single_scope_body(
                    space_id=space_id,
                    memory_scope_id=memory_scope_id,
                    thread_id=thread_id,
                    space_slug=space_slug,
                    memory_scope_external_ref=memory_scope_external_ref,
                    thread_external_ref=thread_external_ref,
                ),
                "filename": filename,
                "content_type": content_type,
                "classification": classification,
                "extract": extract,
                "parser_profile": parser_profile,
            }
        )
        headers = {"Content-Type": content_type} if content_type else None
        return self._request(
            "POST",
            "/v1/assets",
            params=params,
            content=content,
            headers=headers,
        )

    def list_assets(
        self,
        *,
        space_id: str | None = None,
        memory_scope_id: str | None = None,
        thread_id: str | None = None,
        space_slug: str | None = None,
        memory_scope_external_ref: str | None = None,
        thread_external_ref: str | None = None,
        status: str | None = "stored",
        limit: int = 50,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/v1/assets",
            params=_payloads.without_none(
                {
                    **_payloads.single_scope_body(
                        space_id=space_id,
                        memory_scope_id=memory_scope_id,
                        thread_id=thread_id,
                        space_slug=space_slug,
                        memory_scope_external_ref=memory_scope_external_ref,
                        thread_external_ref=thread_external_ref,
                    ),
                    "status": status,
                    "limit": limit,
                }
            ),
        )

    def get_asset(self, asset_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/assets/{asset_id}")

    def delete_asset(self, asset_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/v1/assets/{asset_id}")

    def download_asset(self, asset_id: str) -> bytes:
        return self._request_bytes("GET", f"/v1/assets/{asset_id}/download")

    def request_asset_extraction(
        self,
        asset_id: str,
        *,
        parser_profile: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1/assets/{asset_id}/extractions",
            params=_payloads.without_none({"parser_profile": parser_profile}),
        )

    def list_asset_extractions(
        self,
        asset_id: str,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/v1/assets/{asset_id}/extractions",
            params=_payloads.without_none({"status": status, "limit": limit}),
        )

    def list_scope_asset_extractions(
        self,
        *,
        space_id: str | None = None,
        memory_scope_id: str | None = None,
        thread_id: str | None = None,
        space_slug: str | None = None,
        memory_scope_external_ref: str | None = None,
        thread_external_ref: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/v1/asset-extractions",
            params=_payloads.without_none(
                {
                    **_payloads.single_scope_body(
                        space_id=space_id,
                        memory_scope_id=memory_scope_id,
                        thread_id=thread_id,
                        space_slug=space_slug,
                        memory_scope_external_ref=memory_scope_external_ref,
                        thread_external_ref=thread_external_ref,
                    ),
                    "status": status,
                    "limit": limit,
                }
            ),
        )

    def get_asset_extraction(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/asset-extractions/{job_id}")

    def retry_asset_extraction(self, job_id: str) -> dict[str, Any]:
        return self._request("POST", f"/v1/asset-extractions/{job_id}/retry")

    def cancel_asset_extraction(self, job_id: str) -> dict[str, Any]:
        return self._request("POST", f"/v1/asset-extractions/{job_id}/cancel")

    def download_extraction_artifact(self, artifact_id: str) -> bytes:
        return self._request_bytes(
            "GET",
            f"/v1/extraction-artifacts/{artifact_id}/download",
        )
