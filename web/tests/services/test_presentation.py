from web.services.presentation import summarize_run, summarize_trend


def _metric(item_id, dimension, layer, name, scope, value):
    return {"run_item_id": item_id, "dimension": dimension, "layer": layer,
            "metric_name": name, "scope": scope, "value": value}


def test_cq2term_summary_keeps_overall_scores_and_aggregates_cq_coverage():
    run = {"items": [{"id": "item-1", "task": "cq2term", "domain": "awo"}], "metrics": [
        _metric("item-1", "term", "terms", "precision", "combined", 0.8),
        _metric("item-1", "term", "terms", "recall", "combined", 1.0),
        _metric("item-1", "term", "terms", "f1", "combined", 0.8888888),
        _metric("item-1", "term", "terms", "f1", "class_only", 1.0),
        _metric("item-1", "term", "cq_coverage", "coverage", "cq:CQ1", 1.0),
        _metric("item-1", "term", "cq_coverage", "coverage", "cq:CQ2", 0.5),
    ]}

    summary = summarize_run(run)

    assert [entry["label"] for entry in summary] == [
        "综合精确率", "综合召回率", "综合 F1", "CQ 平均覆盖率"]
    assert summary[-1]["value"] == 0.75
    assert summary[-1]["scope"] == "per_cq_mean"
    assert all(entry["domain"] == "awo" for entry in summary)


def test_trend_compares_the_same_summary_key_not_repeated_metric_names():
    item = {"id": "item-1", "task": "cq2term", "domain": "awo"}
    previous = {"items": [item], "metrics": [
        _metric("item-1", "term", "terms", "precision", "combined", 0.6),
        _metric("item-1", "term", "terms", "recall", "combined", 1.0),
        _metric("item-1", "term", "cq_coverage", "coverage", "cq:CQ1", 0.5),
    ]}
    current = {"items": [item], "metrics": [
        _metric("item-1", "term", "terms", "precision", "combined", 0.8),
        _metric("item-1", "term", "terms", "recall", "combined", 1.0),
        _metric("item-1", "term", "cq_coverage", "coverage", "cq:CQ1", 0.75),
    ]}

    deltas = summarize_trend(current, previous)

    assert [(entry["label"], round(entry["delta"], 2), entry["improved"])
            for entry in deltas] == [
                ("综合精确率", 0.2, True),
                ("综合召回率", 0.0, None),
                ("CQ 平均覆盖率", 0.25, True),
            ]


def test_cq2onto_summary_distinguishes_global_strict_and_closure_scores():
    run = {"items": [{"id": "onto", "task": "cq2onto", "domain": "wine"}], "metrics": [
        _metric("onto", "class", "aggregated", "f1", "aggregate", 0.8),
        _metric("onto", "property", "aggregated", "f1", "aggregate", 0.7),
        _metric("onto", "triple", "layer4_global", "f1", "global", 0.6),
        _metric("onto", "axiom", "layer4", "f1", "global", 0.5),
        _metric("onto", "hierarchy", "closure", "f1", "closure", 0.9),
        _metric("onto", "axiom", "cq_coverage", "average_cq_coverage", "strict", 0.4),
        _metric("onto", "hierarchy", "cq_coverage", "average_cq_coverage", "closure", 0.75),
    ]}

    assert [entry["label"] for entry in summarize_run(run)] == [
        "类 F1", "属性 F1", "三元组 F1（全局）", "公理 F1（全局）", "层级 F1（闭包）",
        "CQ 平均覆盖率（严格）", "CQ 平均覆盖率（闭包）"]
