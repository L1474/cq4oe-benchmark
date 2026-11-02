import json

from web.app import create_app
from web.config import Settings
from fastapi.testclient import TestClient


class FakeWorker:
    def run_forever(self, stop):
        stop.wait()


def make_page_client(tmp_path):
    project = tmp_path / "project"
    for task, slug, cq_id, question in (
        ("CQ2Term", "alpha_cq2term_cqs.json", "T1", "term question private text?"),
        ("CQ2Onto", "alpha_cq2onto_cqs.json", "O1", "ontology question private text?"),
    ):
        folder = project / task / "competency_question"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / slug).write_text(json.dumps([{"id": cq_id, "value": question}]), encoding="utf-8")
    app = create_app(Settings(project, tmp_path / "data"), lambda settings, readiness: FakeWorker())
    return TestClient(app)


def test_page_routes_render_and_domain_list_keeps_questions_in_detail(tmp_path):
    client = make_page_client(tmp_path)
    with client:
        home = client.get("/", follow_redirects=False)
        assert home.status_code == 307
        assert home.headers["location"] == "/runs/new"
        for path in ("/agents", "/runs/new", "/guide", "/evaluation-guide", "/domains", "/domains/alpha"):
            response = client.get(path)
            assert response.status_code == 200, path
            assert "text/html" in response.headers["content-type"]
            assert 'href="/records"' in response.text
        domain_list = client.get("/domains").text
        assert "term question private text?" not in domain_list
        assert "ontology question private text?" not in domain_list


def test_run_form_uses_task_domain_controls_and_task_specific_counts(tmp_path):
    client = make_page_client(tmp_path)
    with client:
        page = client.get("/runs/new").text
        assert page.count('aria-current="page"') == 1
        assert 'data-cq-count-for="cq2term"' in page
        assert 'data-cq-count-for="cq2onto"' in page
        assert 'id="run-task"' in page
        assert 'id="run-domain"' in page
        assert 'id="add-item"' in page
        assert 'id="selected-items"' in page
        assert 'class="domain-selection"' not in page
        assert 'id="accept-confirmation" disabled' in page
        assert 'id="open-checklist"' in page
        assert "每个任务 / 领域上传一个文件" in page
        assert 'href="/guide"' in page


def test_model_form_uses_name_only_and_guide_explains_external_inputs(tmp_path):
    client = make_page_client(tmp_path)
    with client:
        agents = client.get("/agents").text
        assert 'id="model-name"' in agents
        assert 'id="model-base-url"' not in agents
        assert "API Key" not in agents
        guide = client.get("/guide").text
        assert "prediction_template.json" in guide
        assert "ontology/" in guide
        assert "log/" in guide
        assert "normal" in guide and "cqbycq" in guide and "agent" in guide


def test_evaluation_guide_has_task_and_dimension_tabs(tmp_path):
    client = make_page_client(tmp_path)
    with client:
        page = client.get("/evaluation-guide").text
        assert 'id="guide-tab-cq2term"' in page
        assert 'id="guide-tab-cq2onto"' in page
        for tab in ("methods", "alignment", "characteristics", "triple", "axiom", "hierarchy", "coverage", "report"):
            assert f'id="onto-tab-{tab}"' in page
        assert "不会把答在别的 CQ 下的词项算作本题覆盖" in page
        assert "Layer 2 · 语义候选" in page
        assert "Layer 4 · 全局范围" in page
        assert "只统计已对齐属性对" in page
        assert "不是 Web 把一组分数机械填进固定表格" in page
        assert "mismatch" in page
        assert "HermiT" in page
        assert "03 domain / range 三元组" in page
        assert "严格未命中但闭包能够证明" in page
        assert "Property-Axiom (Triple)" in page


def test_domain_detail_exposes_task_cqs_and_task_bundle_links(tmp_path):
    client = make_page_client(tmp_path)
    with client:
        page = client.get("/domains/alpha").text
        assert "term question private text?" in page
        assert "ontology question private text?" in page
        assert "/api/catalog/cq2term/alpha/bundle" in page
        assert "/api/catalog/cq2onto/alpha/bundle" in page
        assert "预测产物格式" in page
        assert "OWL、RDF/XML、Turtle、N-Triples 或 N3" in page


def test_records_and_compare_pages_render_and_detail_sanitizes_report(tmp_path):
    from web.repositories import (add_artifact, add_event, create_agent, create_model,
                                  create_run, save_metrics, save_stage_state)

    client = make_page_client(tmp_path)
    app = client.app
    with client:
        records = client.get("/records")
        assert records.status_code == 200
        assert 'id="records-body"' in records.text
        assert 'id="trend-toggle"' in records.text
        assert client.get("/compare").status_code == 200

        agent = create_agent(app.state.settings.database_path, user_id="local", name="A")
        model = create_model(app.state.settings.database_path, user_id="local", agent_id=agent["id"],
                             name="M", provider="ollama", model_id="m")
        runs = [create_run(app.state.settings.database_path, user_id="local", agent_id=agent["id"],
                           model_id=model["id"], items=[{"task": "cq2onto", "domain": "alpha"}],
                           config={}, runs_root=app.state.settings.runs_root, initial_status="completed")
                for _ in range(2)]
        run = runs[0]
        add_event(app.state.settings.database_path, user_id="local", run_id=run["id"],
                  event_type="stage", payload={"stage": "class", "text": "example detailed log line"})
        save_stage_state(app.state.settings.database_path, user_id="local", run_id=run["id"],
                         run_item_id=run["items"][0]["id"], stage="hierarchy", status="completed")
        save_stage_state(app.state.settings.database_path, user_id="local", run_id=run["id"],
                         run_item_id=run["items"][0]["id"], stage="class", status="completed")
        save_metrics(app.state.settings.database_path, user_id="local", run_id=run["id"], metrics=[{
            "run_item_id": run["items"][0]["id"], "dimension": "class", "layer": "aggregated",
            "metric_name": "f1", "scope": "aggregate", "value": 0.555555, "unit": "ratio",
        }])
        report = "# Report\n\n<script>alert(1)</script>\n\n## Class\n\n| Metric | Value |\n| --- | --- |\n| F1 | 0.5 |\n"
        report_path = app.state.settings.runs_root / run["id"] / "results" / "report.md"
        report_path.parent.mkdir(parents=True)
        report_path.write_text(report, encoding="utf-8")
        add_artifact(app.state.settings.database_path, user_id="local", run_id=run["id"], run_item_id=None,
                     category="results", relative_path="results/report.md", media_type="text/markdown",
                     size_bytes=len(report), sha256="x", name="report.md")
        other_path = app.state.settings.runs_root / run["id"] / "items" / run["items"][0]["id"] / "results" / "report.md"
        other_path.parent.mkdir(parents=True, exist_ok=True)
        other_path.write_text("# Property\n\nSecond complete report.", encoding="utf-8")
        add_artifact(app.state.settings.database_path, user_id="local", run_id=run["id"],
                     run_item_id=run["items"][0]["id"], category="results",
                     relative_path=f"items/{run['items'][0]['id']}/results/report.md",
                     media_type="text/markdown", size_bytes=32, sha256="y", name="report.md")

        detail = client.get(f"/runs/{run['id']}")
        assert detail.status_code == 200
        assert "<script>" not in detail.text
        assert "alert(1)" in detail.text
        assert "<table>" in detail.text
        assert 'href="#report-1-class"' in detail.text
        assert 'id="report-1-class"' in detail.text
        assert "Second complete report." in detail.text
        assert "中文指标摘要" in detail.text
        assert "查看原始英文报告" in detail.text
        assert "0.56" in detail.text
        assert "原始 report.md 由 CQ2Term / CQ2Onto 评测脚本生成" in detail.text
        assert 'data-open-log-drawer' in detail.text
        assert 'id="log-drawer"' in detail.text
        assert 'id="log-stage-filter"' in detail.text
        assert 'id="log-stream-filter"' in detail.text
        assert 'class="event-list"' not in detail.text
        assert "example detailed log line" not in detail.text
        class_stage = detail.text.index("类评测")
        hierarchy_stage = detail.text.index("层级闭包评测")
        assert class_stage < hierarchy_stage
        assert 'href="#report-2-property"' in detail.text
        assert "CQ2ONTO / alpha" in detail.text
        assert '<pre>{}</pre>' in detail.text
        comparison = client.get(f"/compare?run_ids={runs[0]['id']},{runs[1]['id']}")
        assert comparison.status_code == 200
        assert 'data-compare-view="summary"' in comparison.text
        assert 'data-compare-view="all"' in comparison.text


def test_artifact_list_distinguishes_duplicate_names_by_item(tmp_path):
    from web.repositories import add_artifact, create_agent, create_model, create_run

    client = make_page_client(tmp_path)
    app = client.app
    with client:
        agent = create_agent(app.state.settings.database_path, user_id="local", name="A")
        model = create_model(app.state.settings.database_path, user_id="local", agent_id=agent["id"],
                             name="M", provider="ollama", model_id="m")
        run = create_run(app.state.settings.database_path, user_id="local", agent_id=agent["id"],
                         model_id=model["id"], items=[{"task": "cq2term", "domain": "alpha"},
                                                        {"task": "cq2onto", "domain": "alpha"}],
                         config={}, runs_root=app.state.settings.runs_root)
        for item in run["items"]:
            relative = f"items/{item['id']}/results/summary/report.md"
            path = app.state.settings.runs_root / run["id"] / relative
            path.parent.mkdir(parents=True)
            path.write_text(f"# {item['task']}", encoding="utf-8")
            add_artifact(app.state.settings.database_path, user_id="local", run_id=run["id"],
                         run_item_id=item["id"], category="results", relative_path=relative,
                         media_type="text/markdown", size_bytes=8, sha256="x", name="report.md")

        detail = client.get(f"/runs/{run['id']}")

        assert "CQ2TERM / alpha · results/summary/report.md" in detail.text
        assert "CQ2ONTO / alpha · results/summary/report.md" in detail.text
