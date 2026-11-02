from web.i18n import metric_description, scope_label


def test_cq_scope_and_metric_description_identify_which_question_is_scored():
    metric = {"dimension": "term", "layer": "cq_coverage", "metric_name": "coverage", "scope": "cq:CQ14"}

    assert scope_label("cq:CQ14") == "CQ14（逐题）"
    assert "CQ14（逐题）" in metric_description(metric)
    assert "该 CQ 所需词项" in metric_description(metric)
