from pathlib import Path

from infinity_context_server import eval as eval_module


def test_public_benchmark_cli_passes_targeted_case_ids(monkeypatch, capsys, tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    dataset.write_text("[]", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run_public_memory_benchmark(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "suite": "public-memory-benchmark",
            "ok": True,
            "status": "ok",
            "metrics": {},
            "failures": [],
        }

    monkeypatch.setattr(
        eval_module,
        "run_public_memory_benchmark",
        fake_run_public_memory_benchmark,
    )

    eval_module.main(
        [
            "public-benchmark",
            "--dataset",
            str(dataset),
            "--benchmark",
            "locomo",
            "--case-id",
            "locomo:conv-26:qa:60",
            "--case-id",
            "conv-41:qa:46",
            "--min-accuracy",
            "1.0",
        ]
    )

    capsys.readouterr()
    assert captured["dataset_path"] == dataset
    assert captured["benchmark"] == "locomo"
    assert captured["min_accuracy"] == 1.0
    assert captured["case_ids"] == ("locomo:conv-26:qa:60", "conv-41:qa:46")
