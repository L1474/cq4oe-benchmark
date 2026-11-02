"""Select readable headline scores without changing stored evaluator metrics."""

from statistics import fmean


_CQ2TERM = (
    ("term", "terms", "precision", "combined", "precision", "综合精确率",
     "跨全部 CQ 合并类和属性后，预测词项中匹配金标准的比例。"),
    ("term", "terms", "recall", "combined", "recall", "综合召回率",
     "跨全部 CQ 合并类和属性后，金标准词项被预测覆盖的比例。"),
    ("term", "terms", "f1", "combined", "f1", "综合 F1",
     "综合精确率和召回率的调和平均；按全领域词项计算，不区分 CQ。"),
)

_CQ2ONTO = (
    ("class", "aggregated", "f1", "aggregate", "class_f1", "类 F1",
     "生成类与金标准类对齐后的综合 F1。"),
    ("property", "aggregated", "f1", "aggregate", "property_f1", "属性 F1",
     "生成属性与金标准属性对齐后的综合 F1。"),
    ("triple", "layer4_global", "f1", "global", "triple_f1", "三元组 F1（全局）",
     "全部 domain/range 三元组的全局 F1，包含未对齐项。"),
    ("axiom", "layer4", "f1", "global", "axiom_f1", "公理 F1（全局）",
     "全部原子 TBox 公理的全局 F1，包含未对齐项。"),
    ("hierarchy", "closure", "f1", "closure", "hierarchy_f1", "层级 F1（闭包）",
     "HermiT 推理得到的类和属性层级闭包的综合 F1。"),
    ("axiom", "cq_coverage", "average_cq_coverage", "strict", "strict_cq_coverage", "CQ 平均覆盖率（严格）",
     "直接匹配到的公理在各 CQ 所需公理中的平均覆盖比例。"),
    ("hierarchy", "cq_coverage", "average_cq_coverage", "closure", "closure_cq_coverage", "CQ 平均覆盖率（闭包）",
     "计入推理闭包补救结果后，各 CQ 所需公理的平均覆盖比例。"),
)


def _score(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def summarize_run(run: dict) -> list[dict]:
    summary = []
    metrics = run.get("metrics", [])
    for item in run.get("items", []):
        task, domain = item["task"], item["domain"]
        item_metrics = [metric for metric in metrics if metric.get("run_item_id") == item["id"]]
        by_key = {(m["dimension"], m["layer"], m["metric_name"], m["scope"]): m
                  for m in item_metrics}
        for dimension, layer, name, scope, code, label, description in (
                _CQ2TERM if task == "cq2term" else _CQ2ONTO if task == "cq2onto" else ()):
            metric = by_key.get((dimension, layer, name, scope))
            if metric is not None:
                summary.append({"key": [task, domain, code], "task": task, "domain": domain,
                                "dimension": dimension, "layer": layer, "metric_name": name, "scope": scope,
                                "label": label, "description": description, "value": _score(metric.get("value"))})
        if task == "cq2term":
            coverage = [_score(m.get("value")) for m in item_metrics
                        if m.get("dimension") == "term" and m.get("layer") == "cq_coverage"
                        and m.get("metric_name") == "coverage" and m.get("scope", "").startswith("cq:")]
            coverage = [value for value in coverage if value is not None]
            if coverage:
                summary.append({"key": [task, domain, "cq_mean"], "task": task, "domain": domain,
                                "dimension": "term", "layer": "cq_coverage", "metric_name": "average_cq_coverage",
                                "scope": "per_cq_mean",
                                "label": "CQ 平均覆盖率",
                                "description": "逐 CQ 计算所需类和属性的覆盖比例，再对该领域的 CQ 取平均。",
                                "value": fmean(coverage)})
    return summary


def summarize_trend(current: dict, previous: dict) -> list[dict]:
    previous_by_key = {tuple(metric["key"]): metric for metric in summarize_run(previous)}
    deltas = []
    for metric in summarize_run(current):
        old = previous_by_key.get(tuple(metric["key"]))
        if old is None or metric["value"] is None or old["value"] is None:
            continue
        delta = metric["value"] - old["value"]
        deltas.append({**metric, "previous": old["value"], "delta": delta,
                       "improved": True if delta > 0 else False if delta < 0 else None})
    return deltas
