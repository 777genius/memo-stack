"""Summarize LoCoMo public benchmark failures from an existing report.

The script is intentionally report-only: it does not inspect datasets or answers
outside the benchmark output, so it can be used for targeted reruns without
introducing benchmark leakage into application code.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--summary-out", type=Path, default=None)
    parser.add_argument("--case-id-out", type=Path, default=None)
    parser.add_argument("--benchmark-args-out", type=Path, default=None)
    parser.add_argument(
        "--capability",
        action="append",
        default=None,
        help=(
            "Include only matching capabilities/categories. Can be repeated or "
            "comma-separated, for example locomo_category_1,category_3."
        ),
    )
    parser.add_argument(
        "--reason",
        action="append",
        default=None,
        help="Include only matching failure reasons. Can be repeated or comma-separated.",
    )
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit selected failures after filtering; useful for small canary reruns.",
    )
    args = parser.parse_args(argv)

    report = _load_report(args.report)
    failures = _filter_failures(
        _failures(report),
        capabilities=_normalize_filters(args.capability),
        reasons=_normalize_filters(args.reason),
    )
    if args.limit is not None:
        failures = failures[: max(0, args.limit)]
    case_ids = [str(item.get("case_id") or "") for item in failures if item.get("case_id")]
    if args.case_id_out is not None:
        args.case_id_out.parent.mkdir(parents=True, exist_ok=True)
        args.case_id_out.write_text(
            "\n".join(case_ids) + ("\n" if case_ids else ""),
            encoding="utf-8",
        )
    if args.benchmark_args_out is not None:
        args.benchmark_args_out.parent.mkdir(parents=True, exist_ok=True)
        args.benchmark_args_out.write_text(_benchmark_args(case_ids), encoding="utf-8")

    summary = _summary(failures, top=args.top)
    if args.summary_out is not None:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _load_report(path: Path) -> Mapping[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, Mapping):
        raise SystemExit(f"report must be a JSON object: {path}")
    return value


def _failures(report: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    failures = report.get("failures")
    if isinstance(failures, list):
        return tuple(item for item in failures if isinstance(item, Mapping))
    cases = report.get("cases")
    if isinstance(cases, list):
        return tuple(
            item
            for item in cases
            if isinstance(item, Mapping) and str(item.get("status") or "") != "ok"
        )
    return ()


def _summary(failures: Sequence[Mapping[str, object]], *, top: int) -> dict[str, object]:
    capabilities: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    missing_terms: Counter[str] = Counter()
    missing_evidence_refs: Counter[str] = Counter()
    missing_evidence_ref_previews: Counter[str] = Counter()
    capability_reasons: dict[str, Counter[str]] = defaultdict(Counter)
    answer_shapes: Counter[str] = Counter()
    failure_patterns: Counter[tuple[str, str]] = Counter()
    query_patterns: Counter[str] = Counter()
    query_pattern_examples: dict[str, list[dict[str, str]]] = defaultdict(list)
    for failure in failures:
        capability = str(failure.get("capability") or failure.get("category") or "unknown")
        reason = str(failure.get("reason") or "unknown")
        answer_shape = _answer_shape(failure)
        capabilities[capability] += 1
        reasons[reason] += 1
        capability_reasons[capability][reason] += 1
        answer_shapes[answer_shape] += 1
        patterns = _query_patterns(failure)
        query_patterns.update(patterns)
        question = _question_text(failure)
        case_id = str(failure.get("case_id") or "")
        for pattern in patterns:
            if question and len(query_pattern_examples[pattern]) < 5:
                query_pattern_examples[pattern].append(
                    {"case_id": case_id, "question": question}
                )
        failure_patterns[(capability, reason)] += 1
        missing_terms.update(_strings(failure.get("missing_terms")))
        missing_evidence_refs.update(_strings(failure.get("missing_evidence_refs")))
        missing_evidence_ref_previews.update(_strings(failure.get("missing_evidence_ref_previews")))

    return {
        "failure_count": len(failures),
        "case_ids": [str(item.get("case_id")) for item in failures[:top] if item.get("case_id")],
        "capability_failure_count": dict(capabilities.most_common()),
        "reason_count": dict(reasons.most_common()),
        "answer_shape_count": dict(answer_shapes.most_common()),
        "failure_pattern_count": {
            f"{capability}:{reason}": count
            for (capability, reason), count in failure_patterns.most_common(top)
        },
        "query_pattern_count": dict(query_patterns.most_common(top)),
        "query_pattern_examples": {
            pattern: examples
            for pattern, examples in sorted(query_pattern_examples.items())
        },
        "capability_reason_count": {
            capability: dict(counter.most_common())
            for capability, counter in sorted(capability_reasons.items())
        },
        "top_missing_terms": dict(missing_terms.most_common(top)),
        "top_missing_evidence_refs": dict(missing_evidence_refs.most_common(top)),
        "top_missing_evidence_ref_previews": dict(
            missing_evidence_ref_previews.most_common(top)
        ),
    }


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if isinstance(item, str) and item)


def _filter_failures(
    failures: Sequence[Mapping[str, object]],
    *,
    capabilities: Sequence[str],
    reasons: Sequence[str],
) -> tuple[Mapping[str, object], ...]:
    if not capabilities and not reasons:
        return tuple(failures)
    capability_set = frozenset(capabilities)
    reason_set = frozenset(reasons)
    return tuple(
        failure
        for failure in failures
        if (not capability_set or _capability_key(failure) in capability_set)
        and (not reason_set or _reason_key(failure) in reason_set)
    )


def _normalize_filters(values: Sequence[str] | None) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    if not values:
        return ()
    for raw_value in values:
        for item in str(raw_value).split(","):
            normalized = item.strip().lower()
            if not normalized:
                continue
            if normalized.startswith("category_"):
                normalized = f"locomo_{normalized}"
            if normalized.startswith("category-"):
                normalized = "locomo_" + normalized.replace("-", "_")
            if normalized not in seen:
                selected.append(normalized)
                seen.add(normalized)
    return tuple(selected)


def _capability_key(failure: Mapping[str, object]) -> str:
    return str(failure.get("capability") or failure.get("category") or "unknown").lower()


def _reason_key(failure: Mapping[str, object]) -> str:
    return str(failure.get("reason") or "unknown").lower()


def _answer_shape(failure: Mapping[str, object]) -> str:
    raw = failure.get("answer_shape") or failure.get("question_type")
    if isinstance(raw, str) and raw:
        return raw
    question = _question_text(failure).casefold()
    if question.startswith(("how many", "number of", "count ")):
        return "count"
    if question.startswith(("when", "what date", "which date")):
        return "when"
    if question.startswith("where"):
        return "where"
    if question.startswith("why"):
        return "why"
    if question.startswith(("did ", "does ", "do ", "is ", "are ", "was ", "were ")):
        return "yes_no"
    if question.startswith(("what ", "which ")):
        plural_markers = (
            " activities",
            " areas",
            " books",
            " cities",
            " countries",
            " events",
            " hobbies",
            " items",
            " places",
            " projects",
            " things",
            " ways",
        )
        if any(marker in question for marker in plural_markers):
            return "list"
        return "what"
    return "unknown"


def _query_patterns(failure: Mapping[str, object]) -> tuple[str, ...]:
    question = _question_text(failure).casefold()
    patterns: list[str] = []
    if "persue" in question or "pursu" in question:
        patterns.append("pursue_typo_or_stem")
    if "preform" in question:
        patterns.append("perform_typo")
    if "reminder of" in question or "remind" in question:
        patterns.append("sentimental_reminder")
    if "motivat" in question or question.startswith("why "):
        patterns.append("motivation_or_reason")
    if question.startswith("when ") or "how long" in question:
        patterns.append("temporal_answer")
    if any(
        marker in question
        for marker in (
            "what books",
            "what activities",
            "what games",
            "what recipes",
            "what events",
        )
    ):
        patterns.append("list_inventory")
    if any(marker in question for marker in ("both", "common", "share")):
        patterns.append("commonality")
    if any(marker in question for marker in ("lgbtq", "transgender", "identity")):
        patterns.append("identity_community")
    return tuple(patterns or ("other",))


def _question_text(failure: Mapping[str, object]) -> str:
    return str(
        failure.get("question")
        or failure.get("question_preview")
        or failure.get("query")
        or ""
    )


def _benchmark_args(case_ids: Sequence[str]) -> str:
    return "".join(f"--case-id {case_id}\n" for case_id in case_ids)


if __name__ == "__main__":
    raise SystemExit(main())
