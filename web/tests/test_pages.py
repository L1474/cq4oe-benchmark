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
        assert "Prediction input" in page
        assert "OWL, RDF/XML, Turtle, N-Triples, or N3" in page
