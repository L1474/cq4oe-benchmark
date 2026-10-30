import sqlite3

from fastapi.responses import JSONResponse

from web.db import connect_database


def health_response(settings, readiness):
    try:
        with connect_database(settings.database_path) as connection:
            schema = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='agents'"
            ).fetchone()
            if schema is None:
                raise sqlite3.DatabaseError("application schema unavailable")
        database = "ok"
    except (sqlite3.Error, OSError):
        database = "unavailable"
    embedding = "ready" if readiness and readiness.is_ready() else "starting"
    healthy = database == "ok"
    return JSONResponse(
        {"status": "ok" if healthy else "unhealthy", "database": database, "embedding": embedding},
        status_code=200 if healthy else 503,
    )
