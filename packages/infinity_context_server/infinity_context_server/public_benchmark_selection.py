"""Case selection helpers for public memory benchmark runs."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, TypeVar

CASE_SELECTION_FIRST = "first"
CASE_SELECTION_STRATIFIED = "stratified"
SUPPORTED_CASE_SELECTION_STRATEGIES = frozenset(
    {CASE_SELECTION_FIRST, CASE_SELECTION_STRATIFIED}
)


class PublicBenchmarkSelectableCase(Protocol):
    benchmark: str
    case_id: str


TCase = TypeVar("TCase", bound=PublicBenchmarkSelectableCase)
ErrorFactory = Callable[[str], Exception]
CapabilityResolver = Callable[[TCase], str]


def select_cases(
    cases: Sequence[TCase],
    *,
    max_cases: int | None,
    strategy: str,
    case_ids: Sequence[str] | None = None,
    capabilities: Sequence[str] | None = None,
    capability_resolver: CapabilityResolver[TCase],
    error_factory: ErrorFactory = ValueError,
) -> tuple[tuple[TCase, ...], dict[str, object]]:
    normalized_strategy = normalize_case_selection_strategy(
        strategy,
        error_factory=error_factory,
    )
    available = tuple(cases)
    if max_cases is not None and max_cases < 1:
        raise error_factory("max_cases must be greater than zero")
    requested_case_ids = normalize_requested_case_ids(case_ids)
    requested_capabilities = normalize_requested_capabilities(capabilities)
    selection_pool = _filter_cases_by_capability(
        available,
        requested_capabilities=requested_capabilities,
        capability_resolver=capability_resolver,
    )
    if requested_case_ids:
        selected_by_id = tuple(
            case
            for case in selection_pool
            if _case_matches_requested_case_ids(case, requested_case_ids)
        )
        selected_ids = {_case_selection_identity(case) for case in selected_by_id}
        selected_ids.update(case.case_id for case in selected_by_id)
        missing_case_ids = tuple(
            case_id for case_id in requested_case_ids if case_id not in selected_ids
        )
        return selected_by_id, _case_selection_report(
            available=available,
            selection_pool=selection_pool,
            selected=selected_by_id,
            max_cases=max_cases,
            strategy="case-id",
            requested_case_ids=requested_case_ids,
            missing_case_ids=missing_case_ids,
            requested_capabilities=requested_capabilities,
            missing_capabilities=_missing_requested_capabilities(
                available,
                requested_capabilities=requested_capabilities,
                capability_resolver=capability_resolver,
            ),
            capability_resolver=capability_resolver,
        )
    if max_cases is None or max_cases >= len(selection_pool):
        selected = selection_pool
    elif normalized_strategy == CASE_SELECTION_FIRST:
        selected = selection_pool[:max_cases]
    else:
        selected = _stratified_case_selection(
            selection_pool,
            max_cases=max_cases,
            capability_resolver=capability_resolver,
        )
    return selected, _case_selection_report(
        available=available,
        selection_pool=selection_pool,
        selected=selected,
        max_cases=max_cases,
        strategy=normalized_strategy,
        requested_capabilities=requested_capabilities,
        missing_capabilities=_missing_requested_capabilities(
            available,
            requested_capabilities=requested_capabilities,
            capability_resolver=capability_resolver,
        ),
        capability_resolver=capability_resolver,
    )


def normalize_requested_case_ids(case_ids: Sequence[str] | None) -> tuple[str, ...]:
    if not case_ids:
        return ()
    selected: list[str] = []
    seen: set[str] = set()
    for raw_case_id in case_ids:
        for item in str(raw_case_id).split(","):
            case_id = item.strip()
            if not case_id or case_id in seen:
                continue
            selected.append(case_id)
            seen.add(case_id)
    return tuple(selected)


def normalize_requested_capabilities(capabilities: Sequence[str] | None) -> tuple[str, ...]:
    if not capabilities:
        return ()
    raw_values = (capabilities,) if isinstance(capabilities, str) else tuple(capabilities)
    selected: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        for item in str(raw_value).split(","):
            capability = _normalize_capability_filter(item)
            if not capability or capability in seen:
                continue
            selected.append(capability)
            seen.add(capability)
    return tuple(selected)


def normalize_case_selection_strategy(
    value: str,
    *,
    error_factory: ErrorFactory = ValueError,
) -> str:
    normalized = (value or "").strip().lower().replace("_", "-")
    if normalized in {"", CASE_SELECTION_FIRST}:
        return CASE_SELECTION_FIRST
    if normalized == CASE_SELECTION_STRATIFIED:
        return CASE_SELECTION_STRATIFIED
    raise error_factory(f"Unsupported case selection strategy: {value}")


def case_selection_missing_case_ids(
    case_selection: Mapping[str, object] | None,
) -> tuple[str, ...]:
    return _safe_tuple(case_selection, "missing_case_ids")


def case_selection_missing_capabilities(
    case_selection: Mapping[str, object] | None,
) -> tuple[str, ...]:
    return _safe_tuple(case_selection, "missing_capabilities")


def missing_case_id_failures(case_ids: Sequence[str]) -> list[dict[str, object]]:
    return [
        {
            "case_id": case_id,
            "category": "setup",
            "reason": "requested_case_id_not_found",
        }
        for case_id in case_ids
    ]


def missing_capability_failures(capabilities: Sequence[str]) -> list[dict[str, object]]:
    return [
        {
            "case_id": "case_selection",
            "category": "setup",
            "reason": "requested_capability_not_found",
            "capability": capability,
        }
        for capability in capabilities
    ]


def _filter_cases_by_capability(
    cases: Sequence[TCase],
    *,
    requested_capabilities: Sequence[str],
    capability_resolver: CapabilityResolver[TCase],
) -> tuple[TCase, ...]:
    if not requested_capabilities:
        return tuple(cases)
    return tuple(
        case
        for case in cases
        if _case_matches_requested_capabilities(
            case,
            requested_capabilities=requested_capabilities,
            capability_resolver=capability_resolver,
        )
    )


def _case_matches_requested_capabilities(
    case: TCase,
    *,
    requested_capabilities: Sequence[str],
    capability_resolver: CapabilityResolver[TCase],
) -> bool:
    capability = _case_capability(case, capability_resolver=capability_resolver)
    group = _case_selection_group(case, capability_resolver=capability_resolver)
    return any(capability == item or group == item for item in requested_capabilities)


def _case_matches_requested_case_ids(
    case: TCase,
    requested_case_ids: Sequence[str],
) -> bool:
    identities = {case.case_id, _case_selection_identity(case)}
    return any(case_id in identities for case_id in requested_case_ids)


def _stratified_case_selection(
    cases: Sequence[TCase],
    *,
    max_cases: int,
    capability_resolver: CapabilityResolver[TCase],
) -> tuple[TCase, ...]:
    grouped: dict[str, list[TCase]] = defaultdict(list)
    for case in cases:
        grouped[_case_selection_group(case, capability_resolver=capability_resolver)].append(case)
    selected: list[TCase] = []
    round_index = 0
    ordered_groups = sorted(grouped)
    while len(selected) < max_cases:
        added = False
        for group in ordered_groups:
            group_cases = grouped[group]
            if round_index >= len(group_cases):
                continue
            selected.append(group_cases[round_index])
            added = True
            if len(selected) >= max_cases:
                break
        if not added:
            break
        round_index += 1
    return tuple(selected)


def _case_selection_report(
    *,
    available: Sequence[TCase],
    selection_pool: Sequence[TCase],
    selected: Sequence[TCase],
    max_cases: int | None,
    strategy: str,
    requested_case_ids: Sequence[str] = (),
    missing_case_ids: Sequence[str] = (),
    requested_capabilities: Sequence[str] = (),
    missing_capabilities: Sequence[str] = (),
    capability_resolver: CapabilityResolver[TCase],
) -> dict[str, object]:
    available_counts = _case_selection_counts(
        available,
        capability_resolver=capability_resolver,
    )
    selected_counts = _case_selection_counts(
        selected,
        capability_resolver=capability_resolver,
    )
    report: dict[str, object] = {
        "schema_version": "public-benchmark-case-selection-v1",
        "strategy": strategy,
        "requested_max_cases": max_cases,
        "input_case_count": len(available),
        "selection_pool_case_count": len(selection_pool),
        "selected_case_count": len(selected),
        "truncated": len(selected) < len(selection_pool),
        "available_capability_count": len(available_counts),
        "selected_capability_count": len(selected_counts),
        "available_capability_counts": available_counts,
        "selected_capability_counts": selected_counts,
    }
    if requested_case_ids:
        report["requested_case_ids"] = list(requested_case_ids)
        report["requested_case_id_count"] = len(requested_case_ids)
        report["missing_case_ids"] = list(missing_case_ids)
        report["missing_case_id_count"] = len(missing_case_ids)
    if requested_capabilities:
        report["requested_capabilities"] = list(requested_capabilities)
        report["requested_capability_count"] = len(requested_capabilities)
        report["missing_capabilities"] = list(missing_capabilities)
        report["missing_capability_count"] = len(missing_capabilities)
        report["capability_filter_applied"] = True
    return report


def _missing_requested_capabilities(
    cases: Sequence[TCase],
    *,
    requested_capabilities: Sequence[str],
    capability_resolver: CapabilityResolver[TCase],
) -> tuple[str, ...]:
    if not requested_capabilities:
        return ()
    available = set(_case_selection_counts(cases, capability_resolver=capability_resolver))
    available.update(
        _case_capability(case, capability_resolver=capability_resolver)
        for case in cases
    )
    return tuple(item for item in requested_capabilities if item not in available)


def _case_selection_counts(
    cases: Sequence[TCase],
    *,
    capability_resolver: CapabilityResolver[TCase],
) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for case in cases:
        counts[_case_selection_group(case, capability_resolver=capability_resolver)] += 1
    return dict(sorted(counts.items()))


def _case_selection_group(
    case: TCase,
    *,
    capability_resolver: CapabilityResolver[TCase],
) -> str:
    capability = _case_capability(case, capability_resolver=capability_resolver)
    return f"{case.benchmark}:{capability}"


def _case_capability(
    case: TCase,
    *,
    capability_resolver: CapabilityResolver[TCase],
) -> str:
    return _normalize_capability_part(capability_resolver(case)) or "uncategorized"


def _case_selection_identity(case: PublicBenchmarkSelectableCase) -> str:
    return f"{case.benchmark}:{case.case_id}"


def _safe_tuple(
    case_selection: Mapping[str, object] | None,
    key: str,
) -> tuple[str, ...]:
    if not isinstance(case_selection, Mapping):
        return ()
    values = case_selection.get(key)
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return ()
    selected: list[str] = []
    for item in values:
        value = str(item).strip()
        if value:
            selected.append(value)
    return tuple(selected)


def _normalize_capability_filter(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    raw = value.strip()
    benchmark, separator, capability = raw.partition(":")
    if not separator:
        return _normalize_capability_part(raw)
    normalized_benchmark = benchmark.strip().casefold().replace("_", "-").replace(" ", "-")
    normalized_capability = _normalize_capability_part(capability)
    if not normalized_benchmark or not normalized_capability:
        return ""
    return f"{normalized_benchmark}:{normalized_capability}"


def _normalize_capability_part(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
    return "".join(char for char in normalized if char.isalnum() or char == "_").strip("_")
