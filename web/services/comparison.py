import json
from dataclasses import dataclass
from typing import Any


MetricKey = tuple[str, str, str, str, str, str, str]


@dataclass(frozen=True)
class MetricDelta:
    current: dict | None
    previous: dict | None
    delta: float | None
    comparable: bool
    reason: str | None
    improved: bool | None


@dataclass(frozen=True)
class MetricComparison:
    key: MetricKey
    entries: list[MetricDelta]


@dataclass(frozen=True)
class ComparisonResult:
    run_ids: list[str]
    domains: list[str]
    intersection_count: int
    metrics: list[MetricComparison]


def _canonical(value: Any) -> str:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
    return json.dumps(value or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _item_set(run: dict) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((item.get("task", ""), item.get("domain", "")) for item in run.get("items", [])))


def find_previous_comparable_run(current_run: dict, candidates: list[dict]) -> dict | None:
    if current_run.get("status") != "completed":
        return None
    current_date = current_run.get("created_at", "")
    eligible = []
    for candidate in candidates:
        if candidate.get("id") == current_run.get("id") or candidate.get("status") != "completed":
            continue
        if candidate.get("created_at", "") >= current_date:
            continue
        if any(candidate.get(field) != current_run.get(field)
               for field in ("agent_id", "model_id", "evaluator_version", "gold_fingerprint")):
            continue
        if _canonical(candidate.get("config_json", candidate.get("config"))) != _canonical(
                current_run.get("config_json", current_run.get("config"))):
            continue
        if _item_set(candidate) != _item_set(current_run):
            continue
        eligible.append(candidate)
    return max(eligible, key=lambda run: (run.get("created_at", ""), run.get("id", "")), default=None)


def _metric_key(metric: dict, items_by_id: dict[str, dict]) -> MetricKey:
    item = items_by_id.get(metric.get("run_item_id"), {})
    return (item.get("task", metric.get("task", "")), item.get("domain", metric.get("domain", "")),
            metric.get("dimension", ""), metric.get("layer", ""), metric.get("metric_name", ""),
            metric.get("unit") or "", metric.get("scope", ""))


def _improved(metric_name: str, delta: float) -> bool | None:
    if delta == 0:
        return None
    name = metric_name.lower()
    if name in {"f1", "precision", "recall", "coverage", "any_cq_coverage", "fully_cq_coverage",
                "average_cq_coverage"}:
        return delta > 0
    if name in {"fp", "fn", "false_positive", "false_positives", "false_negative", "false_negatives",
                "mismatch", "mismatches"}:
        return delta < 0
    return None


def compare_runs(run_records: list[dict]) -> ComparisonResult:
    if not 2 <= len(run_records) <= 4:
        raise ValueError("select between two and four runs")
    domain_sets = [{item.get("domain", "") for item in run.get("items", [])} for run in run_records]
    domains = sorted(set.intersection(*domain_sets)) if domain_sets else []
    maps = []
    all_keys = set()
    for run in run_records:
        items_by_id = {item.get("id"): item for item in run.get("items", [])}
        metric_map = {}
        for metric in run.get("metrics", []):
            key = _metric_key(metric, items_by_id)
            if key[1] in domains:
                metric_map[key] = metric
                all_keys.add(key)
        maps.append(metric_map)

    metric_comparisons = []
    for key in sorted(all_keys):
        baseline = maps[0].get(key)
        entries = []
        for index, metric_map in enumerate(maps):
            current = metric_map.get(key)
            if index == 0:
                entries.append(MetricDelta(current, None, None, bool(current),
                                           None if current else "metric_key_mismatch", None))
                continue
            if baseline is None or current is None:
                entries.append(MetricDelta(current, baseline, None, False, "metric_key_mismatch", None))
                continue
            try:
                delta = float(current["value"]) - float(baseline["value"])
            except (KeyError, TypeError, ValueError):
                entries.append(MetricDelta(current, baseline, None, False, "non_numeric_value", None))
                continue
            entries.append(MetricDelta(current, baseline, delta, True, None, _improved(key[4], delta)))
        metric_comparisons.append(MetricComparison(key, entries))
    return ComparisonResult([str(run.get("id", "")) for run in run_records], domains, len(domains), metric_comparisons)
