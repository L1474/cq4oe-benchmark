import csv
import json
from pathlib import Path

from web.types import MetricRecord, RunPaths


def _read_json(path: Path) -> dict:
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _num(block: dict, key: str):
    value = block.get(key)
    return int(value) if isinstance(value, (int, float)) and value is not None else None


def _prf(records: list[MetricRecord], dimension: str, layer: str, block: dict,
         scope: str, unit: str = "ratio") -> None:
    tp, fp, fn = (_num(block, key) for key in ("tp", "fp", "fn"))
    for name in ("precision", "recall", "f1"):
        value = block.get(name)
        denominator = (tp + fp if name == "precision" and tp is not None and fp is not None else
                       tp + fn if name == "recall" and tp is not None and fn is not None else None)
        numerator = tp if name != "f1" else None
        records.append(MetricRecord(dimension, layer, name,
            float(value) if isinstance(value, (int, float)) else None, unit, scope,
            tp, fp, fn, numerator, denominator))


def _coverage(records: list[MetricRecord], dimension: str, layer: str,
              name: str, value, scope: str, numerator=None, denominator=None) -> None:
    records.append(MetricRecord(dimension, layer, name,
        float(value) if isinstance(value, (int, float)) else None, "ratio", scope,
        numerator=numerator, denominator=denominator))


def extract_cq2term_metrics(result_json: Path, coverage_csv: Path) -> list[MetricRecord]:
    doc = _read_json(result_json)
    result = doc.get("results", {})
    records: list[MetricRecord] = []
    overall = result.get("metrics_overall", {})
    for group, metric_block in overall.items():
        if isinstance(metric_block, dict):
            _prf(records, "term", "terms", metric_block, group)
    for entry in result.get("per_cq_coverage", []) or []:
        denom = entry.get("n_gold_classes", 0) + entry.get("n_gold_properties", 0)
        num = entry.get("n_covered_classes", 0) + entry.get("n_covered_properties", 0)
        _coverage(records, "term", "cq_coverage", "coverage", entry.get("coverage"),
                  f"cq:{entry.get('cq_id', '')}", num, denom)
    csv_path = Path(coverage_csv)
    if not any(m.layer == "cq_coverage" for m in records) and csv_path.exists():
        with csv_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                try:
                    value = float(row.get("coverage", ""))
                except (TypeError, ValueError):
                    value = None
                total = sum(int(row.get(key) or 0) for key in ("n_gold_classes", "n_gold_properties"))
                covered = sum(int(row.get(key) or 0) for key in ("n_covered_classes", "n_covered_properties"))
                _coverage(records, "term", "cq_coverage", "coverage", value,
                          f"cq:{row.get('cq_id', '')}", covered, total)
    return records


def _items_by_id(data) -> dict:
    if isinstance(data, list):
        return {entry.get("id"): entry for entry in data if isinstance(entry, dict)}
    return data if isinstance(data, dict) else {}


def _result_sections(doc: dict) -> dict:
    results = doc.get("results")
    if results is None:
        return {key: value for key, value in doc.items() if key != "config"}
    if isinstance(results, list):
        return _items_by_id(results)
    return results if isinstance(results, dict) else {}


def _read_item(paths: RunPaths, relative: str) -> dict:
    return _read_json(paths.results / relative)


def _extract_prf_scope(records, dimension, layer, block, scope):
    if isinstance(block, dict) and any(k in block for k in ("precision", "recall", "f1")):
        _prf(records, dimension, layer, block, scope)


def _counts_as_prf(block: dict, *, mismatch_as_both: bool = False) -> dict:
    tp, fp, fn = (_num(block, key) for key in ("tp", "fp", "fn"))
    if tp is None or fp is None or fn is None:
        return block
    if mismatch_as_both:
        mismatch = _num(block, "mismatch") or 0
        fp += mismatch
        fn += mismatch
    pden, rden = tp + fp, tp + fn
    precision = tp / pden if pden else None
    recall = tp / rden if rden else None
    f1 = (2 * precision * recall / (precision + recall) if precision + recall else 0.0
          ) if precision is not None and recall is not None else None
    return {**block, "tp": tp, "fp": fp, "fn": fn,
            "precision": precision, "recall": recall, "f1": f1}


def extract_cq2onto_metrics(result_paths: RunPaths) -> list[MetricRecord]:
    records: list[MetricRecord] = []
    class_doc = _read_item(result_paths, "01_class/class_result.json")
    class_sections = _result_sections(class_doc)
    aggregated_class = class_doc.get("aggregated_overall", class_sections.get("aggregated_overall", {}))
    _extract_prf_scope(records, "class", "aggregated", aggregated_class, "aggregate")

    property_doc = _read_item(result_paths, "02_property/property_result.json")
    property_sections = _result_sections(property_doc)
    aggregated_property = property_doc.get("aggregated_overall", property_sections.get("aggregated_overall", {}))
    _extract_prf_scope(records, "property", "aggregated", aggregated_property, "aggregate")
    prop = property_sections
    char_block = prop.get("characteristics_check", {})
    for scope, key in (("alignment_conditioned", "overall"), ("global", "overall_ontology")):
        _extract_prf_scope(records, "property_characteristic", "characteristics", char_block.get(key, {}), scope)
    # Some evaluator versions save the characteristic output as a sibling JSON.
    char_doc = _read_item(result_paths, "02_property/property_characteristics.json")
    for scope, key in (("alignment_conditioned", "overall"), ("global", "overall_ontology")):
        _extract_prf_scope(records, "property_characteristic", "characteristics", char_doc.get(key, {}), scope)

    triple = _result_sections(_read_item(result_paths, "03_triple/triple_result.json"))
    for section, key, scope in (("layer2_semantic", "overall", "semantic"),
                                ("layer3_strict", "grand_overall", "alignment_conditioned"),
                                ("layer4_global", "grand_overall", "global")):
        _extract_prf_scope(records, "triple", section, triple.get(section, {}).get(key, {}), scope)

    axiom_doc = _read_item(result_paths, "04_axiom/eval_axioms_result.json")
    ax = axiom_doc.get("results", {})
    for section, scope in (("layer2", "semantic"), ("layer3", "alignment_conditioned"), ("layer4", "global")):
        block = ax.get(section, {})
        overall = block.get("overall", block.get("counts_overall", block.get("grand", {})))
        _extract_prf_scope(records, "axiom", section,
                           _counts_as_prf(overall, mismatch_as_both=section == "layer3"), scope)
        if section == "layer4" and not overall:
            _extract_prf_scope(records, "axiom", section, _counts_as_prf(block.get("grand", {})), scope)
    cov = ax.get("cq_coverage", {})
    for key, label in (("any_coverage", "any_cq_coverage"), ("fully_coverage", "fully_cq_coverage"),
                       ("average_rate", "average_cq_coverage")):
        _coverage(records, "axiom", "cq_coverage", label, cov.get(key), "strict",
                  cov.get("n_any_covered") if key == "any_coverage" else None,
                  cov.get("n_total"))

    hierarchy = _result_sections(_read_item(result_paths, "05_hierarchy/hierarchy_result.json"))
    for label, dimension in (("class_metrics", "class_hierarchy"), ("property_metrics", "property_hierarchy"),
                             ("combined_metrics", "hierarchy")):
        _extract_prf_scope(records, dimension, "closure", hierarchy.get(label, {}), "closure")
    hcov = hierarchy.get("cq_coverage_closure", {})
    for key, label in (("any_coverage", "any_cq_coverage"), ("fully_coverage", "fully_cq_coverage"),
                       ("average_rate", "average_cq_coverage")):
        _coverage(records, "hierarchy", "cq_coverage", label, hcov.get(key), "closure",
                  hcov.get("n_any_covered") if key == "any_coverage" else None, hcov.get("n_total"))
    return records
