import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from web.db import connect_database
from web.domain.bundles import build_cq_bundle
from web.domain.catalog import get_domain_detail, list_domains
from web.repositories import (add_event, create_agent, create_model, get_run, list_agents,
                              list_models, list_runs, resolve_artifact_path)
from web.services.run_service import RunServiceError
from web.services.privacy import redact_paths

api_router = APIRouter()


class AgentInput(BaseModel):
    name: str
    description: str = ""
    config: dict = Field(default_factory=dict)


class ModelInput(BaseModel):
    name: str
    provider: str = "ollama"
    model_id: str
    config: dict = Field(default_factory=dict)


class AgentPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    config: dict | None = None


class ModelPatch(BaseModel):
    name: str | None = None
    provider: str | None = None
    model_id: str | None = None
    config: dict | None = None


class RunItemInput(BaseModel):
    task: str
    domain: str


class RunInput(BaseModel):
    agent_id: str
    model_id: str | None = None
    items: list[RunItemInput]
    config: dict = Field(default_factory=dict)


class ConfirmationInput(BaseModel):
    confirmed_ids: list[str]


def _state(request):
    return request.app.state


def _json_config(row):
    row = dict(row)
    row["config"] = json.loads(row.pop("config_json", "{}"))
    return row


def _dump(model):
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def _public_run(run):
    if run is None:
        return None
    result = dict(run)
    result.pop("run_path", None)
    for item in result.get("items", []):
        item.pop("input_path", None)
        confirmation = item.pop("confirmation_json", None)
        if confirmation:
            item["confirmed_cq_ids"] = json.loads(confirmation)
    result["events"] = [_public_event(event) for event in result.get("events", [])]
    return result


def _public_event(event):
    result = dict(event)
    try:
        result["payload_json"] = json.dumps(redact_paths(json.loads(result.get("payload_json", "{}"))), sort_keys=True)
    except (TypeError, json.JSONDecodeError):
        result["payload_json"] = redact_paths(str(result.get("payload_json", "{}")))
    return result


@api_router.get("/health")
def health(request: Request):
    ready = request.app.state.readiness.is_ready() if getattr(request.app.state, "readiness", None) else False
    return {"status": "ok", "model_ready": ready}


@api_router.get("/catalog")
def catalog(request: Request):
    return list_domains(_state(request).settings.project_root)


@api_router.get("/catalog/{task}/{domain}")
def catalog_domain(request: Request, task: str, domain: str):
    try:
        detail = get_domain_detail(_state(request).settings.project_root, domain)
    except KeyError:
        raise HTTPException(404, "Domain not found")
    if task not in detail["tasks"]:
        raise HTTPException(404, "Task not found for domain")
    return {"slug": detail["slug"], "name": detail["name"], "task": task, **detail["tasks"][task]}


@api_router.get("/catalog/{task}/{domain}/bundle")
def catalog_bundle(request: Request, task: str, domain: str):
    try:
        content = build_cq_bundle(_state(request).settings.project_root, task, domain)
    except (KeyError, FileNotFoundError, ValueError):
        raise HTTPException(404, "CQ bundle not found")
    return Response(content, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{domain}-{task}-cqs.zip"'})


@api_router.get("/agents")
def agents(request: Request):
    return [_json_config(row) for row in list_agents(_state(request).settings.database_path, user_id="local")]


@api_router.post("/agents", status_code=201)
def create_agent_route(request: Request, body: AgentInput):
    return _json_config(create_agent(_state(request).settings.database_path, user_id="local", **_dump(body)))


@api_router.patch("/agents/{agent_id}")
def update_agent(request: Request, agent_id: str, body: AgentPatch):
    db = _state(request).settings.database_path
    values = _dump(body)
    if "config" in values:
        values["config_json"] = json.dumps(values.pop("config"), sort_keys=True)
    values = {key: value for key, value in values.items() if value is not None}
    if not values:
        raise HTTPException(400, "No agent fields supplied")
    assignments = ",".join(f"{key}=?" for key in values)
    with connect_database(db) as conn:
        cursor = conn.execute(f"UPDATE agents SET {assignments} WHERE id=? AND user_id='local'",
                              (*values.values(), agent_id))
        if cursor.rowcount != 1:
            raise HTTPException(404, "Agent not found")
        return _json_config(conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone())


@api_router.delete("/agents/{agent_id}", status_code=204)
def delete_agent(request: Request, agent_id: str):
    with connect_database(_state(request).settings.database_path) as conn:
        cursor = conn.execute("DELETE FROM agents WHERE id=? AND user_id='local'", (agent_id,))
        if cursor.rowcount != 1:
            raise HTTPException(404, "Agent not found")
    return Response(status_code=204)


@api_router.get("/agents/{agent_id}/models")
def models(request: Request, agent_id: str):
    with connect_database(_state(request).settings.database_path) as conn:
        if not conn.execute("SELECT 1 FROM agents WHERE id=? AND user_id='local'", (agent_id,)).fetchone():
            raise HTTPException(404, "Agent not found")
    return [_json_config(row) for row in list_models(_state(request).settings.database_path,
                                                     user_id="local", agent_id=agent_id)]


@api_router.post("/agents/{agent_id}/models", status_code=201)
def create_model_route(request: Request, agent_id: str, body: ModelInput):
    with connect_database(_state(request).settings.database_path) as conn:
        if not conn.execute("SELECT 1 FROM agents WHERE id=? AND user_id='local'", (agent_id,)).fetchone():
            raise HTTPException(404, "Agent not found")
    return _json_config(create_model(_state(request).settings.database_path, user_id="local",
                                     agent_id=agent_id, **_dump(body)))


@api_router.patch("/models/{model_id}")
def update_model(request: Request, model_id: str, body: ModelPatch):
    values = _dump(body)
    if "config" in values:
        values["config_json"] = json.dumps(values.pop("config"), sort_keys=True)
    values = {key: value for key, value in values.items() if value is not None}
    if not values:
        raise HTTPException(400, "No model fields supplied")
    assignments = ",".join(f"{key}=?" for key in values)
    with connect_database(_state(request).settings.database_path) as conn:
        cursor = conn.execute(f"UPDATE models SET {assignments} WHERE id=? AND user_id='local'",
                              (*values.values(), model_id))
        if cursor.rowcount != 1:
            raise HTTPException(404, "Model not found")
        return _json_config(conn.execute("SELECT * FROM models WHERE id=?", (model_id,)).fetchone())


@api_router.delete("/models/{model_id}", status_code=204)
def delete_model(request: Request, model_id: str):
    with connect_database(_state(request).settings.database_path) as conn:
        cursor = conn.execute("DELETE FROM models WHERE id=? AND user_id='local'", (model_id,))
        if cursor.rowcount != 1:
            raise HTTPException(404, "Model not found")
    return Response(status_code=204)


@api_router.post("/runs", status_code=201)
def create_run_route(request: Request, body: RunInput):
    service = _state(request).run_service
    try:
        run_id = service.create_draft_run("local", body.agent_id, body.model_id,
                                          [_dump(item) for item in body.items], body.config)
    except (RunServiceError, sqlite3.IntegrityError) as exc:
        raise HTTPException(400, str(exc))
    return _public_run(get_run(_state(request).settings.database_path, user_id="local", run_id=run_id))


@api_router.put("/runs/{run_id}/items/{item_id}/confirmation")
def confirm_item(request: Request, run_id: str, item_id: str, body: ConfirmationInput):
    try:
        _state(request).run_service.set_confirmation(run_id, item_id, body.confirmed_ids)
    except RunServiceError as exc:
        raise HTTPException(400, str(exc))
    return {"confirmed": True}


@api_router.post("/runs/{run_id}/items/{item_id}/upload", status_code=201)
def upload_item(request: Request, run_id: str, item_id: str, file: UploadFile = File(...)):
    try:
        return _state(request).run_service.save_item_upload(run_id, item_id, file)
    except RunServiceError as exc:
        raise HTTPException(400, str(exc))


@api_router.post("/runs/{run_id}/start")
def start_run(request: Request, run_id: str):
    try:
        _state(request).run_service.start_run(run_id)
    except RunServiceError as exc:
        raise HTTPException(400, str(exc))
    return _public_run(get_run(_state(request).settings.database_path, user_id="local", run_id=run_id))


@api_router.get("/runs")
def runs(request: Request):
    return [_public_run(run) for run in list_runs(_state(request).settings.database_path, user_id="local")]


@api_router.get("/runs/{run_id}")
def run_detail(request: Request, run_id: str):
    run = get_run(_state(request).settings.database_path, user_id="local", run_id=run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return _public_run(run)


@api_router.get("/runs/{run_id}/events")
def run_events(request: Request, run_id: str):
    run = get_run(_state(request).settings.database_path, user_id="local", run_id=run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return [_public_event(event) for event in run["events"]]


@api_router.get("/artifacts/{artifact_id}")
def artifact_download(request: Request, artifact_id: str):
    db = _state(request).settings.database_path
    with connect_database(db) as conn:
        row = conn.execute("SELECT a.*,r.run_path FROM artifacts a JOIN runs r ON r.id=a.run_id WHERE a.id=? AND a.user_id='local'", (artifact_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Artifact not found")
    try:
        path = resolve_artifact_path(Path(row["run_path"]), dict(row))
    except ValueError:
        raise HTTPException(404, "Artifact not found")
    if not path.is_file():
        raise HTTPException(404, "Artifact file not found")
    return FileResponse(path, media_type=row["media_type"], filename=row["name"])
