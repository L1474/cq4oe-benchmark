import json
from html.parser import HTMLParser
from pathlib import Path

import bleach
import markdown
from markdown.extensions.toc import slugify

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web.db import connect_database
from web.domain.catalog import get_domain_detail, list_domains
from web.repositories import get_run, list_agents, resolve_artifact_path
from web.i18n import (dimension_label, event_label, layer_label, metric_label,
                      scope_label, stage_label, status_label, task_label, unit_label)

pages_router = APIRouter()


@pages_router.get("/", include_in_schema=False)
def home_page():
    return RedirectResponse("/runs/new", status_code=307)


class _ReportHeadings(HTMLParser):
    def __init__(self):
        super().__init__()
        self.headings = []
        self._heading_id = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag in {"h1", "h2", "h3"}:
            self._heading_id = dict(attrs).get("id")
            self._text = []

    def handle_data(self, data):
        if self._heading_id:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag in {"h1", "h2", "h3"} and self._heading_id:
            self.headings.append({"id": self._heading_id, "text": "".join(self._text).lower()})
            self._heading_id = None


def _report_sections(safe_html: str) -> list[dict]:
    parser = _ReportHeadings()
    parser.feed(safe_html)
    sections = []
    for label in ("Class", "Property", "Triple", "Axiom", "Hierarchy"):
        candidates = [heading for heading in parser.headings if label.lower() in heading["text"]]
        if label == "Property":
            candidates = [heading for heading in candidates if "triple" not in heading["text"]]
        if candidates:
            sections.append({"label": label, "id": candidates[0]["id"]})
    return sections


def _templates(request: Request) -> Jinja2Templates:
    templates = Jinja2Templates(directory=str(request.app.state.settings.web_root / "templates"))
    templates.env.filters.update({
        "dimension_label": dimension_label,
        "layer_label": layer_label,
        "metric_label": metric_label,
        "scope_label": scope_label,
        "status_label": status_label,
        "task_label": task_label,
        "unit_label": unit_label,
        "stage_label": stage_label,
        "event_label": event_label,
    })
    return templates


@pages_router.get("/agents", response_class=HTMLResponse)
def agents_page(request: Request):
    return _templates(request).TemplateResponse(request, "agents.html", {})


@pages_router.get("/guide", response_class=HTMLResponse)
def guide_page(request: Request):
    return _templates(request).TemplateResponse(request, "guide.html", {})


@pages_router.get("/runs/new", response_class=HTMLResponse)
def new_run_page(request: Request):
    domains = list_domains(request.app.state.settings.project_root)
    return _templates(request).TemplateResponse(request, "runs_new.html", {"domains": domains})


@pages_router.get("/domains", response_class=HTMLResponse)
def domains_page(request: Request):
    domains = list_domains(request.app.state.settings.project_root)
    return _templates(request).TemplateResponse(request, "domains.html", {"domains": domains})


@pages_router.get("/domains/{domain}", response_class=HTMLResponse)
def domain_detail_page(request: Request, domain: str):
    try:
        detail = get_domain_detail(request.app.state.settings.project_root, domain)
    except KeyError:
        raise HTTPException(status_code=404, detail="Domain not found")
    return _templates(request).TemplateResponse(request, "domain_detail.html", {"domain": detail})


@pages_router.get("/records", response_class=HTMLResponse)
def records_page(request: Request):
    database = request.app.state.settings.database_path
    return _templates(request).TemplateResponse(request, "records.html", {
        "agents": list_agents(database, user_id="local"), "domains": list_domains(request.app.state.settings.project_root),
        "tasks": ("cq2term", "cq2onto"),
    })


@pages_router.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail_page(request: Request, run_id: str):
    run = get_run(request.app.state.settings.database_path, user_id="local", run_id=run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    for item in run["items"]:
        item["confirmed_cq_ids"] = json.loads(item["confirmation_json"]) if item["confirmation_json"] else []
    with connect_database(request.app.state.settings.database_path) as connection:
        agent = connection.execute("SELECT name FROM agents WHERE id=? AND user_id='local'", (run["agent_id"],)).fetchone()
        model = connection.execute("SELECT name,model_id,provider FROM models WHERE id=? AND user_id='local'", (run["model_id"],)).fetchone()
    for artifact in run["artifacts"]:
        artifact["download_url"] = f"/api/runs/{run_id}/artifacts/{artifact['id']}"
        item = next((item for item in run["items"] if item["id"] == artifact["run_item_id"]), None)
        if item:
            prefix = f"items/{item['id']}/"
            relative = artifact["relative_path"]
            within_item = relative[len(prefix):] if relative.startswith(prefix) else f"{artifact['category']}/{artifact['name']}"
            artifact["context_label"] = f"{item['task'].upper()} / {item['domain']} · {within_item}"
        else:
            artifact["context_label"] = f"运行 · {artifact['category']}/{artifact['name']}"
    reports = []
    report_artifacts = [artifact for artifact in run["artifacts"] if artifact["name"].lower() == "report.md"]
    for index, report_artifact in enumerate(report_artifacts, start=1):
        try:
            report_path = resolve_artifact_path(Path(run["run_path"]), report_artifact)
            report_source = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
            raw_html = markdown.markdown(report_source, extensions=["tables", "toc"],
                extension_configs={"toc": {"slugify": lambda text, sep, prefix=index: f"report-{prefix}-{slugify(text, sep)}"}})
            report_html = bleach.clean(raw_html,
                tags={"h1", "h2", "h3", "h4", "p", "ul", "ol", "li", "table", "thead", "tbody", "tr", "th", "td", "pre", "code", "strong", "em", "a", "hr", "blockquote", "br"},
                attributes={"a": ["href", "title"], "h1": ["id"], "h2": ["id"], "h3": ["id"], "h4": ["id"]},
                protocols={"http", "https", "mailto"})
            item = next((item for item in run["items"] if item["id"] == report_artifact["run_item_id"]), None)
            reports.append({"html": report_html, "sections": _report_sections(report_html),
                            "artifact": report_artifact, "item": item})
        except (OSError, UnicodeError, ValueError):
            continue
    return _templates(request).TemplateResponse(request, "run_detail.html", {
        "run": run, "agent": dict(agent) if agent else {"name": "未知 Agent"},
        "model": dict(model) if model else {"name": "未知模型", "model_id": "", "provider": ""},
        "reports": reports, "config": json.loads(run["config_json"]),
    })


@pages_router.get("/compare", response_class=HTMLResponse)
def compare_page(request: Request, run_ids: str = ""):
    ids = [value for value in run_ids.split(",") if value]
    if len(ids) > 4:
        raise HTTPException(status_code=422, detail="Select no more than four runs")
    records = []
    for run_id in ids:
        run = get_run(request.app.state.settings.database_path, user_id="local", run_id=run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        records.append(run)
    return _templates(request).TemplateResponse(request, "compare.html", {"runs": records})
