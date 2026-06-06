from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import httpx
from memo_stack_server_harness import python_env, run_memo_stack_server


def test_memory_digest_http_and_cli_e2e(tmp_path: Path) -> None:
    with (
        run_memo_stack_server(tmp_path, database_name="digest.db") as server,
        httpx.Client(
            base_url=server.base_url,
            headers={"Authorization": f"Bearer {server.token}"},
            timeout=5,
        ) as client,
    ):
        marker = f"DIGEST_E2E_{time.time_ns()}"
        fact_text = f"{marker}: Graphiti is the temporal graph projection."
        suggestion_text = f"{marker}: memory_digest should stay read-only and evidence-only."
        fact_response = client.post(
            "/v1/facts",
            json={
                "space_slug": "digest-e2e",
                "profile_external_ref": "default",
                "text": fact_text,
                "kind": "architecture_decision",
                "source_refs": [{"source_type": "manual", "source_id": f"{marker}:fact"}],
            },
            headers={"Idempotency-Key": f"{marker}:fact"},
        )
        assert fact_response.status_code == 201, fact_response.text
        suggestion_response = client.post(
            "/v1/suggestions",
            json={
                "space_slug": "digest-e2e",
                "profile_external_ref": "default",
                "candidate_text": suggestion_text,
                "kind": "architecture_decision",
                "safe_reason": "pending review",
                "source_refs": [
                    {"source_type": "manual", "source_id": f"{marker}:suggestion"}
                ],
            },
        )
        assert suggestion_response.status_code == 201, suggestion_response.text

        digest_response = client.post(
            "/v1/digest",
            json={
                "space_slug": "digest-e2e",
                "profile_external_ref": "default",
                "topic": marker,
                "max_chunks": 0,
                "include_related": False,
            },
        )
        assert digest_response.status_code == 200, digest_response.text
        digest = digest_response.json()["data"]
        assert digest["diagnostics"]["evidence_only"] is True
        assert fact_text in digest["rendered_markdown"]
        assert suggestion_text in digest["rendered_markdown"]
        assert "not_canonical" in digest["rendered_markdown"]

        env = python_env(
            {
                "MEMORY_MCP_API_URL": server.base_url,
                "MEMORY_MCP_AUTH_TOKEN": server.token,
                "MEMO_STACK_HOME": str(tmp_path / "cli-home"),
            }
        )
        cli = subprocess.run(
            [
                sys.executable,
                "-m",
                "memo_stack_cli",
                "digest",
                marker,
                "--space",
                "digest-e2e",
                "--profile",
                "default",
                "--max-chunks",
                "0",
                "--no-related",
            ],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        assert cli.returncode == 0, cli.stderr
        assert fact_text in cli.stdout
        assert suggestion_text in cli.stdout
        assert server.token not in cli.stdout
        assert server.token not in cli.stderr
