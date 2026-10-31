import json
import pytest

from web.services.metrics import extract_cq2onto_metrics, extract_cq2term_metrics
from web.types import RunPaths


def test_cq2term_extracts_aggregate_and_per_cq_coverage(tmp_path):
    result = tmp_path / "result.json"
    result.write_text(json.dumps({"results": {
        "metrics_overall": {"combined": {"tp": 2, "fp": 1, "fn": 2,
            "precision": 2 / 3, "recall": 0.5, "f1": 4 / 7}},
        "per_cq_coverage": [{"cq_id": "CQ1", "coverage": 0.5,
                             "n_gold_classes": 2, "n_gold_properties": 0}],
    }}), encoding="utf-8")
    coverage = tmp_path / "coverage.csv"
    coverage.write_text("cq_id,coverage\nCQ1,0.5\n", encoding="utf-8")

    records = extract_cq2term_metrics(result, coverage)

    assert any(m.dimension == "term" and m.metric_name == "f1" and
               m.tp == 2 and m.scope == "combined" for m in records)
    cq = next(m for m in records if m.metric_name == "coverage")
    assert cq.scope == "cq:CQ1"
    assert cq.denominator == 2


def test_cq2onto_keeps_scopes_distinct_and_null_empty_metrics(tmp_path):
    paths = RunPaths(tmp_path)
    paths.ensure()
    fixtures = {
        "01_class/class_result.json": {"results": [{"id": "aggregated_overall",
            "tp": 1, "fp": 0, "fn": 1, "precision": 1, "recall": 0.5, "f1": 2 / 3}]},
        "02_property/property_result.json": {"results": [
            {"id": "aggregated_overall", "tp": 0, "fp": 0, "fn": 0,
             "precision": None, "recall": None, "f1": None},
            {"id": "characteristics_check", "overall": {
                "tp": 1, "fp": 0, "fn": 1, "precision": 1, "recall": 0.5, "f1": 2 / 3},
             "overall_ontology": {"tp": 0, "fp": 0, "fn": 2, "precision": None, "recall": 0, "f1": None}}]},
        "03_triple/triple_result.json": {"results": [
            {"id": "layer2_semantic", "overall": {
            "tp": 1, "fp": 1, "fn": 1, "precision": 0.5, "recall": 0.5, "f1": 0.5}},
            {"id": "layer3_strict", "grand_overall": {"tp": 1, "fp": 0, "fn": 1,
            "precision": 1, "recall": 0.5, "f1": 2 / 3}},
            {"id": "layer4_global", "grand_overall": {"tp": 1, "fp": 2, "fn": 1,
            "precision": 1 / 3, "recall": 0.5, "f1": 0.4}}]},
        "04_axiom/eval_axioms_result.json": {"results": {
            "layer2": {"overall": {"tp": 1, "fp": 0, "fn": 1, "precision": 1, "recall": 0.5, "f1": 2 / 3}},
            "layer3": {"counts_overall": {"tp": 1, "fp": 1, "fn": 2, "mismatch": 2}},
            "layer4": {"grand": {"tp": 1, "fp": 1, "fn": 1}},
            "cq_coverage": {"n_total": 2, "n_any_covered": 1, "any_coverage": 0.5,
                             "average_rate": 0.25, "fully_coverage": 0}}},
        "05_hierarchy/hierarchy_result.json": {"results": [
            {"id": "class_metrics", "tp": 1, "fp": 0, "fn": 1, "precision": 1, "recall": 0.5, "f1": 2 / 3},
            {"id": "cq_coverage_closure", "n_total": 2, "n_any_covered": 1,
             "any_coverage": 0.5, "average_rate": 0.25, "fully_coverage": 0}]},
    }
    for relative, value in fixtures.items():
        path = paths.results / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    records = extract_cq2onto_metrics(paths)

    assert {m.scope for m in records if m.dimension == "triple" and m.metric_name == "f1"} >= {
        "semantic", "alignment_conditioned", "global"
    }
    empty_f1 = next(m for m in records if m.dimension == "property_characteristic" and
                    m.scope == "global" and m.metric_name == "f1")
    assert empty_f1.value is None
    strict = next(m for m in records if m.dimension == "axiom" and m.layer == "layer3" and
                  m.metric_name == "f1")
    assert (strict.tp, strict.fp, strict.fn) == (1, 3, 4)
    assert strict.value == pytest.approx(2 / 9)
    axiom_coverage = next(m for m in records if m.dimension == "axiom" and
                          m.metric_name == "any_cq_coverage")
    hierarchy_coverage = next(m for m in records if m.dimension == "hierarchy" and
                              m.metric_name == "any_cq_coverage")
    assert axiom_coverage.scope == "strict"
    assert hierarchy_coverage.scope == "closure"
    assert any(m.dimension == "hierarchy" and m.metric_name == "average_cq_coverage" and m.value == 0.25
               for m in records)


@pytest.mark.parametrize("counts, expected", [
    ({"tp": 0, "fp": 2, "fn": 3}, 0.0),
    ({"tp": 0, "fp": 0, "fn": 0}, None),
])
def test_axiom_count_f1_distinguishes_zero_from_undefined(tmp_path, counts, expected):
    paths = RunPaths(tmp_path)
    paths.ensure()
    result = paths.results / "04_axiom/eval_axioms_result.json"
    result.parent.mkdir(parents=True)
    result.write_text(json.dumps({"results": {"layer2": {"overall": counts}}}), encoding="utf-8")

    records = extract_cq2onto_metrics(paths)

    f1 = next(record for record in records if record.dimension == "axiom" and record.metric_name == "f1")
    assert f1.value == expected
