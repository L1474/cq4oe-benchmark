from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from shutil import copyfile
from uuid import uuid4


_CATEGORIES = {"input", "work", "results", "logs"}


@dataclass(frozen=True)
class ArtifactRecord:
    relative_path: str
    size_bytes: int
    sha256: str
    media_type: str
    name: str


def store_artifact(run_root: Path, source: Path, category: str, media_type: str) -> ArtifactRecord:
    run_root = Path(run_root).resolve()
    source = Path(source).resolve(strict=True)
    if category not in _CATEGORIES:
        raise ValueError(f"unsupported artifact category: {category}")
    if not source.is_file() or not source.is_relative_to(run_root):
        raise ValueError("artifact source must be a file inside run root")
    destination_dir = run_root / category
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{uuid4().hex}_{source.name}"
    copyfile(source, destination)
    data = destination.read_bytes()
    return ArtifactRecord(
        relative_path=destination.relative_to(run_root).as_posix(),
        size_bytes=len(data),
        sha256=sha256(data).hexdigest(),
        media_type=media_type,
        name=source.name,
    )
