import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from web.config import Settings, settings_from_environment
from web.db import initialize_database
from web.routes.api import api_router
from web.routes.pages import pages_router
from web.services.model_readiness import ModelReadinessService
from web.services.health import health_response
from web.services.run_service import RunService
from web.services.worker import EvaluationWorker


def create_app(settings: Settings, worker_factory: Callable | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        settings.data_root.mkdir(parents=True, exist_ok=True)
        settings.runs_root.mkdir(parents=True, exist_ok=True)
        initialize_database(settings.database_path)
        readiness = ModelReadinessService(settings.ollama_url)
        worker = (worker_factory(settings, readiness) if worker_factory else
                  EvaluationWorker(settings.database_path, settings.runs_root, readiness,
                                   project_root=settings.project_root,
                                   poll_interval=settings.worker_poll_interval))
        app.state.readiness = readiness
        app.state.worker = worker
        stop_event = threading.Event()
        readiness.start()
        worker_thread = threading.Thread(target=worker.run_forever, args=(stop_event,), name="evaluation-worker", daemon=True)
        worker_thread.start()
        try:
            yield
        finally:
            stop_event.set()
            deadline = time.monotonic() + settings.shutdown_grace_seconds
            worker_thread.join(max(0, deadline - time.monotonic()))
            readiness.stop(max(0, deadline - time.monotonic()))

    app = FastAPI(lifespan=lifespan)
    app.state.settings = settings
    app.state.run_service = RunService(settings.database_path, settings.runs_root, settings.project_root,
                                       settings.max_upload_bytes)
    app.state.readiness = None
    app.include_router(api_router, prefix="/api")
    app.include_router(pages_router)
    app.mount("/static", StaticFiles(directory=settings.web_root / "static"), name="static")

    @app.get("/health")
    def health():
        return health_response(settings, app.state.readiness)

    return app


_root = Path(__file__).resolve().parents[1]
app = create_app(settings_from_environment(_root))
