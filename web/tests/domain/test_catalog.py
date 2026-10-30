import json

import pytest

from web.domain.catalog import get_domain_detail, list_domains


PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parents[3]


def test_catalog_reports_independent_task_specific_counts():
    domains = {item["slug"]: item for item in list_domains(PROJECT_ROOT)}

    assert domains["wine"]["counts"] == {"cq2term": 5, "cq2onto": 5}
    assert domains["swo"]["counts"] == {"cq2term": 26, "cq2onto": 35}
    assert domains["odrl"]["counts"] == {"cq2term": 17, "cq2onto": 18}
    assert domains["odrl"]["source_counts"] == {"cq2term": 19, "cq2onto": 18}
    assert domains["odrl"]["deduplicated_exact_duplicates"] == {"cq2term": 2, "cq2onto": 0}


def test_unknown_domain_raises_key_error():
    with pytest.raises(KeyError):
        get_domain_detail(PROJECT_ROOT, "missing-domain")


def test_absent_task_file_does_not_invent_a_count(tmp_path):
    task_dir = tmp_path / "CQ2Term" / "competency_question"
    task_dir.mkdir(parents=True)
    (task_dir / "sample_cq2term_cqs.json").write_text(
        json.dumps([{"id": "Q1", "value": "Question?"}]), encoding="utf-8"
    )

    domains = list_domains(tmp_path)

    assert domains == [
        {
            "slug": "sample",
            "name": "Sample",
            "counts": {"cq2term": 1},
            "source_counts": {"cq2term": 1},
            "deduplicated_exact_duplicates": {"cq2term": 0},
        }
    ]


def test_domain_detail_contains_task_specific_questions_and_requirements():
    detail = get_domain_detail(PROJECT_ROOT, "wine")

    assert detail["slug"] == "wine"
    assert detail["tasks"]["cq2term"]["count"] == 5
    assert detail["tasks"]["cq2term"]["raw_count"] == 5
    assert detail["tasks"]["cq2onto"]["count"] == 5
    assert all(set(cq) == {"id", "question"} for task in detail["tasks"].values() for cq in task["cqs"])
    assert "class" in detail["tasks"]["cq2term"]["input_requirements"]


def test_conflicting_duplicate_cq_id_is_rejected(tmp_path):
    task_dir = tmp_path / "CQ2Term" / "competency_question"
    task_dir.mkdir(parents=True)
    (task_dir / "sample_cq2term_cqs.json").write_text(
        json.dumps([
            {"id": "Q1", "value": "First question?"},
            {"id": "Q1", "value": "Different question?"},
        ]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="conflicting"):
        list_domains(tmp_path)
