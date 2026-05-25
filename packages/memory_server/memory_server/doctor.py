"""Readiness CLI for Core Lite deployments."""

from __future__ import annotations

import asyncio
import json
import sys

from memory_server.admin import doctor


async def run_doctor() -> dict[str, object]:
    try:
        return await doctor()
    except Exception as exc:
        return {
            "status": "failed",
            "checks": [
                {
                    "name": "postgres",
                    "status": "failed",
                    "safe_error": exc.__class__.__name__,
                }
            ],
        }


def main() -> None:
    result = asyncio.run(run_doctor())
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    sys.exit(0 if result.get("status") == "ok" else 1)


if __name__ == "__main__":
    main()
