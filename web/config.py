from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_root: Path
    database_path: Path | None = None
    max_upload_bytes: int = 50 * 1024 * 1024
    shutdown_grace_seconds: float = 5
    worker_poll_interval: float = 1
    ollama_url: str = "http://127.0.0.1:11434"

    def __post_init__(self):
        object.__setattr__(self, "project_root", Path(self.project_root).resolve())
        object.__setattr__(self, "data_root", Path(self.data_root).resolve())
        if self.database_path is None:
            object.__setattr__(self, "database_path", self.data_root / "evaluator.sqlite3")
        else:
            object.__setattr__(self, "database_path", Path(self.database_path).resolve())

    @property
    def runs_root(self):
        return self.data_root / "runs"
