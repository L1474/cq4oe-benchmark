import pytest

from web.services.comparison import compare_runs, find_previous_comparable_run


def record(run_id, *, created_at="2026-01-01T00:00:00+00:00", status="completed",
           config="{}", gold="gold-a", evaluator="eval-a", model="model-a",
           agent="agent-a", items=None):
    items = items or [{"task": "cq2onto", "domain": "alpha", "id": "item-1"}]
    metrics = []
    for item in items:
        metrics.append({"run_item_id": item["id"], "dimension": "class", "layer": "aggregated",
                        "metric_name": "f1", "value": 0.5, "unit": "ratio", "scope": "aggregate"})
    return {"id": run_id, "created_at": created_at, "status": status, "config_json": config,
            "gold_fingerprint": gold, "evaluator_version": evaluator, "agent_id": agent,
            "model_id": model, "items": items, "metrics": metrics}


def test_matching_metric_keys_get_numeric_deltas_and_direction():
    old = record("old")
    current = record("current")
    old["metrics"][0].update(value=0.4, metric_name="fp")
    current["metrics"][0].update(value=0.2, metric_name="fp")

    result = compare_runs([old, current])

    fp = next(metric for metric in result.metrics if metric.key[4] == "fp")
    assert fp.entries[1].delta == -0.2
    assert fp.entries[1].comparable is True
    assert fp.entries[1].improved is True


def test_metric_scope_mismatch_omits_delta():
    old = record("old")
    current = record("current")
    current["metrics"][0]["scope"] = "global"

    result = compare_runs([old, current])

    metric = result.metrics[0]
    assert metric.entries[1].delta is None
    assert metric.entries[1].comparable is False
    assert metric.entries[1].reason == "metric_key_mismatch"


def test_default_trend_requires_same_fingerprints_config_agent_model_and_item_set():
    current = record("current", created_at="2026-02-01T00:00:00+00:00")
    matching = record("matching", created_at="2026-01-31T00:00:00+00:00")
    bad_gold = record("bad-gold", created_at="2026-01-31T12:00:00+00:00", gold="gold-b")
    failed = record("failed", created_at="2026-01-31T18:00:00+00:00", status="failed")
    partial = record("partial", created_at="2026-01-31T20:00:00+00:00", status="partial")

    result = find_previous_comparable_run(current, [bad_gold, failed, partial, matching])

    assert result["id"] == "matching"


def test_trend_rejects_changed_canonical_config_and_item_set():
    current = record("current", created_at="2026-02-01T00:00:00+00:00", config='{"threshold": 0.5}')
    same_config = record("candidate", created_at="2026-01-31T00:00:00+00:00", config='{"threshold":0.6}')
    same_config["items"][0]["domain"] = "beta"

    assert find_previous_comparable_run(current, [same_config]) is None


def test_explicit_comparison_uses_only_shared_domains():
    first = record("first", items=[{"id": "a", "task": "cq2onto", "domain": "alpha"},
                                    {"id": "b", "task": "cq2onto", "domain": "beta"}])
    second = record("second", items=[{"id": "c", "task": "cq2onto", "domain": "beta"},
                                     {"id": "d", "task": "cq2onto", "domain": "gamma"}])
    first["metrics"][0]["value"] = 0.2
    first["metrics"][1]["value"] = 0.4
    second["metrics"][0]["value"] = 0.5
    second["metrics"][1]["value"] = 0.9

    result = compare_runs([first, second])

    assert result.domains == ["beta"]
    assert result.intersection_count == 1
    assert result.metrics[0].key[1] == "beta"


def test_equal_metric_and_unknown_direction_are_neutral_and_nullable_units_sort():
    old = record("old")
    current = record("current")
    old["metrics"].append({**old["metrics"][0], "metric_name": "cosine", "unit": None, "value": 0.2})
    current["metrics"].append({**current["metrics"][0], "metric_name": "cosine", "unit": None, "value": 0.8})

    result = compare_runs([old, current])

    by_name = {metric.key[4]: metric.entries[1] for metric in result.metrics}
    assert by_name["f1"].delta == 0 and by_name["f1"].improved is None
    assert by_name["cosine"].delta == pytest.approx(0.6) and by_name["cosine"].improved is None
