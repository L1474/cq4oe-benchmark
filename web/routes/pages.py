from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from web.domain.catalog import get_domain_detail, list_domains

pages_router = APIRouter()


def _templates(request: Request) -> Jinja2Templates:
    return Jinja2Templates(directory=str(request.app.state.settings.web_root / "templates"))


@pages_router.get("/agents", response_class=HTMLResponse)
def agents_page(request: Request):
    return _templates(request).TemplateResponse(request, "agents.html", {})


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
