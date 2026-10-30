import json

from web.db import connect_database
from web.repositories import add_artifact, create_agent, create_model, create_run, save_metrics
from web.tests.test_api import make_client


def _record(app, *, agent, model, domain, status="completed", config=None, created_at=None):
    run = create_run(app.state.settings.database_path, user_id="local", agent_id=agent["id"],
                     model_id=model["id"], items=[{"task": "cq2onto", "domain": domain}],
                     config=config or {}, runs_root=app.state.settings.runs_root,
                     evaluator_version="eval", gold_fingerprint="gold", initial_status=status)
    if created_at:
        with connect_database(app.state.settings.database_path) as connection:
            connection.execute("UPDATE runs SET created_at=? WHERE id=?", (created_at, run["id"]))
        run["created_at"] = created_at
    if status == "completed":
        item = run["items"][0]
        save_metrics(app.state.settings.database_path, user_id="local", run_id=run["id"], metrics=[{
            "run_item_id": item["id"], "dimension": "class", "layer": "aggregated",
            "metric_name": "f1", "scope": "aggregate", "unit": "ratio", "value": 0.5,
        }])
    return run


def test_records_filters_compose_and_pagination_are_stable(tmp_path):
    client, app = make_client(tmp_path)
    with client:
        agent = create_agent(app.state.settings.database_path, user_id="local", name="A")
        model = create_model(app.state.settings.database_path, user_id="local", agent_id=agent["id"],
                             name="M", provider="ollama", model_id="m")
        alpha = _record(app, agent=agent, model=model, domain="alpha")
        beta = _record(app, agent=agent, model=model, domain="beta")

        response = client.get("/api/runs", params={"agent_id": agent["id"], "task": "cq2onto",
                                                   "domain": "alpha", "page": 1, "page_size": 1})

        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert [row["id"] for row in response.json()["items"]] == [alpha["id"]]
        assert response.json()["items"][0]["trend"]["previous_run_id"] is None
        assert beta["id"] not in json.dumps(response.json())


def test_task_and_domain_filters_match_the_same_item(tmp_path):
    client, app = make_client(tmp_path)
    with client:
        agent = create_agent(app.state.settings.database_path, user_id="local", name="A")
        model = create_model(app.state.settings.database_path, user_id="local", agent_id=agent["id"],
                             name="M", provider="ollama", model_id="m")
        create_run(app.state.settings.database_path, user_id="local", agent_id=agent["id"],
                   model_id=model["id"], items=[{"task": "cq2term", "domain": "alpha"},
                                                  {"task": "cq2onto", "domain": "beta"}],
                   config={}, runs_root=app.state.settings.runs_root)

        response = client.get("/api/runs", params={"task": "cq2term", "domain": "beta"})

        assert response.json()["total"] == 0


def test_records_trend_returns_only_prior_comparable_run(tmp_path):
    client, app = make_client(tmp_path)
    with client:
        agent = create_agent(app.state.settings.database_path, user_id="local", name="A")
        model = create_model(app.state.settings.database_path, user_id="local", agent_id=agent["id"],
                             name="M", provider="ollama", model_id="m")
        prior = _record(app, agent=agent, model=model, domain="alpha", created_at="2026-10-29T00:00:00+00:00")
        current = _record(app, agent=agent, model=model, domain="alpha", created_at="2026-10-30T00:00:00+00:00")
        response = client.get("/api/runs", params={"trend": "1"})
        row = next(row for row in response.json()["items"] if row["id"] == current["id"])

        assert row["trend"]["previous_run_id"] == prior["id"]
        assert all("run_path" not in row for row in response.json()["items"])


def test_compare_validates_count_and_returns_run_scoped_metrics(tmp_path):
    client, app = make_client(tmp_path)
    with client:
        agent = create_agent(app.state.settings.database_path, user_id="local", name="A")
        model = create_model(app.state.settings.database_path, user_id="local", agent_id=agent["id"],
                             name="M", provider="ollama", model_id="m")
        first = _record(app, agent=agent, model=model, domain="alpha")
        second = _record(app, agent=agent, model=model, domain="alpha")
        assert client.post("/api/runs/compare", json={"run_ids": [first["id"]]}).status_code == 422
        result = client.post("/api/runs/compare", json={"run_ids": [first["id"], second["id"]]})
        assert result.status_code == 200
        assert result.json()["domains"] == ["alpha"]
        assert result.json()["intersection_count"] == 1
        assert result.json()["runs"][0]["model_name"] == "M"
        assert result.json()["runs"][0]["config"] == {}


def test_explicit_compare_rejects_incompatible_evaluator_or_gold_fingerprint(tmp_path):
    client, app = make_client(tmp_path)
    with client:
        agent = create_agent(app.state.settings.database_path, user_id="local", name="A")
        model = create_model(app.state.settings.database_path, user_id="local", agent_id=agent["id"],
                             name="M", provider="ollama", model_id="m")
        first = _record(app, agent=agent, model=model, domain="alpha")
        second = _record(app, agent=agent, model=model, domain="alpha")
        with connect_database(app.state.settings.database_path) as connection:
            connection.execute("UPDATE runs SET gold_fingerprint='different' WHERE id=?", (second["id"],))

        response = client.post("/api/runs/compare", json={"run_ids": [first["id"], second["id"]]})

        assert response.status_code == 422
        assert "fingerprint" in response.json()["detail"]


def test_explicit_compare_accepts_matching_multi_task_runs(tmp_path):
    client, app = make_client(tmp_path)
    with client:
        agent = create_agent(app.state.settings.database_path, user_id="local", name="A")
        model = create_model(app.state.settings.database_path, user_id="local", agent_id=agent["id"],
                             name="M", provider="ollama", model_id="m")
        runs = [create_run(app.state.settings.database_path, user_id="local", agent_id=agent["id"],
                           model_id=model["id"], items=[{"task": "cq2term", "domain": "alpha"},
                                                          {"task": "cq2onto", "domain": "alpha"}],
                           config={}, runs_root=app.state.settings.runs_root,
                           evaluator_version="eval", gold_fingerprint="gold", initial_status="completed")
                for _ in range(2)]

        response = client.post("/api/runs/compare", json={"run_ids": [run["id"] for run in runs]})

        assert response.status_code == 200
        assert response.json()["intersection_count"] == 1


def test_run_detail_lists_artifacts_by_id_without_paths(tmp_path):
    client, app = make_client(tmp_path)
    with client:
        agent = create_agent(app.state.settings.database_path, user_id="local", name="A")
        model = create_model(app.state.settings.database_path, user_id="local", agent_id=agent["id"],
                             name="M", provider="ollama", model_id="m")
        run = _record(app, agent=agent, model=model, domain="alpha")
        root = app.state.settings.runs_root / run["id"]
        (root / "results").mkdir(exist_ok=True)
        (root / "results" / "report.md").write_text("# Report\n\nSafe", encoding="utf-8")
        artifact = add_artifact(app.state.settings.database_path, user_id="local", run_id=run["id"],
                                run_item_id=None, category="results", relative_path="results/report.md",
                                media_type="text/markdown", size_bytes=13, sha256="x", name="report.md")
        response = client.get(f"/api/runs/{run['id']}")

        assert response.status_code == 200
        assert response.json()["artifacts"][0]["id"] == artifact["id"]
        assert "relative_path" not in json.dumps(response.json())
        assert "run_path" not in json.dumps(response.json())
        assert client.get(f"/api/runs/{run['id']}/artifacts/{artifact['id']}").content == (root / "results" / "report.md").read_bytes()


def test_artifact_download_rejects_wrong_run_id(tmp_path):
    client, app = make_client(tmp_path)
    with client:
        agent = create_agent(app.state.settings.database_path, user_id="local", name="A")
        model = create_model(app.state.settings.database_path, user_id="local", agent_id=agent["id"],
                             name="M", provider="ollama", model_id="m")
        first = _record(app, agent=agent, model=model, domain="alpha")
        second = _record(app, agent=agent, model=model, domain="alpha")
        root = app.state.settings.runs_root / first["id"]
        (root / "results").mkdir(exist_ok=True)
        (root / "results" / "x.txt").write_text("private", encoding="utf-8")
        artifact = add_artifact(app.state.settings.database_path, user_id="local", run_id=first["id"],
                                run_item_id=None, category="results", relative_path="results/x.txt",
                                media_type="text/plain", size_bytes=7, sha256="x", name="x.txt")

        assert client.get(f"/api/runs/{second['id']}/artifacts/{artifact['id']}").status_code == 404


def test_records_validate_task_and_date_filters(tmp_path):
    client, _ = make_client(tmp_path)
    with client:
        assert client.get("/api/runs", params={"task": "invalid"}).status_code == 422
        assert client.get("/api/runs", params={"from": "not-a-date"}).status_code == 422
