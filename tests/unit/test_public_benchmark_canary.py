from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
SCRIPT_PATH = ROOT / "scripts" / "official_public_benchmark_canary.py"

spec = importlib.util.spec_from_file_location("official_public_benchmark_canary", SCRIPT_PATH)
assert spec is not None
canary = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = canary
spec.loader.exec_module(canary)


def test_official_public_benchmark_canary_merges_locomo_and_longmemeval_reports(
    tmp_path: Path,
) -> None:
    locomo = tmp_path / "locomo10-mini.json"
    longmemeval = tmp_path / "longmemeval-mini.json"
    report = tmp_path / "official-public-report.json"
    locomo.write_text(
        json.dumps(
            [
                {
                    "sample_id": "conv-mini",
                    "conversation": {
                        "session_1_date_time": "7 May 2023",
                        "session_1": [
                            {
                                "speaker": "Caroline",
                                "dia_id": "D1:1",
                                "text": "I went to the LGBTQ support group today.",
                            }
                        ],
                    },
                    "qa": [
                        {
                            "question": "When did Caroline go to the LGBTQ support group?",
                            "answer": "7 May 2023",
                            "evidence": ["D1:1"],
                            "category": 2,
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    longmemeval.write_text(
        json.dumps(
            [
                {
                    "question_id": "long-mini",
                    "question_type": "single-session-user",
                    "question": "What degree did I graduate with?",
                    "question_date": "2023/05/30 (Tue) 23:40",
                    "answer": "Business Administration",
                    "answer_session_ids": ["answer_session"],
                    "haystack_session_ids": ["answer_session"],
                    "haystack_dates": ["2023/05/20 (Sat) 02:21"],
                    "haystack_sessions": [
                        [
                            {
                                "role": "user",
                                "content": "I graduated with Business Administration.",
                            }
                        ]
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    result = canary.run_official_public_benchmark_canary(
        locomo_dataset=locomo,
        longmemeval_dataset=longmemeval,
        max_cases=1,
        min_accuracy=1.0,
        report_out=report,
    )

    assert result["ok"] is True
    assert result["suite"] == "public-memory-benchmark"
    assert result["benchmark_scope"] == "official_public_memory_retrieval_canary"
    assert result["metrics"]["benchmark_count"] == 2
    assert result["metrics"]["case_count"] == 2
    assert result["metrics"]["accuracy"] == 1.0
    assert {item["name"] for item in result["benchmarks"]} == {"locomo", "longmemeval"}
    assert report.exists()
    assert json.loads(report.read_text(encoding="utf-8"))["ok"] is True


def test_official_public_benchmark_canary_can_run_single_dataset(tmp_path: Path) -> None:
    locomo = tmp_path / "locomo10-mini.json"
    locomo.write_text(
        json.dumps(
            [
                {
                    "sample_id": "conv-mini",
                    "conversation": {
                        "session_1": [
                            {
                                "speaker": "A",
                                "dia_id": "D1:1",
                                "text": "The project codename is Atlas.",
                            }
                        ],
                    },
                    "qa": [
                        {
                            "question": "What is the project codename?",
                            "answer": "Atlas",
                            "evidence": ["D1:1"],
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    result = canary.run_official_public_benchmark_canary(
        benchmark="locomo",
        locomo_dataset=locomo,
        max_cases=1,
        min_accuracy=1.0,
    )

    assert result["ok"] is True
    assert result["metrics"]["benchmark_count"] == 1
    assert result["metrics"]["locomo_case_count"] == 1
    assert result["source_urls"] == {"locomo": canary.LOCOMO_URL}
