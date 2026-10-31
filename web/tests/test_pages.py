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
        for path in ("/agents", "/runs/new", "/domains", "/domains/alpha"):
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
        assert 'data-cq-count-for="cq2term"' in page
        assert 'data-cq-count-for="cq2onto"' in page
        assert 'id="run-task"' in page
        assert 'id="run-domain"' in page
        assert 'id="add-item"' in page
        assert 'id="selected-items"' in page
        assert 'class="domain-selection"' not in page
        assert 'id="accept-confirmation" disabled' in page
        assert 'id="open-checklist"' in page


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
    from web.repositories import add_artifact, create_agent, create_model, create_run

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
        assert 'href="#report-2-property"' in detail.text
        assert "CQ2ONTO / alpha" in detail.text
        assert '<pre>{}</pre>' in detail.text
        assert client.get(f"/compare?run_ids={runs[0]['id']},{runs[1]['id']}").status_code == 200


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
