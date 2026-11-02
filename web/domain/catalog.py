import json
from pathlib import Path


_TASK_DIRS = {"cq2term": "CQ2Term", "cq2onto": "CQ2Onto"}


def _cq_file(project_root: Path, task: str, domain: str) -> Path:
    task_dir = _TASK_DIRS[task]
    return project_root / task_dir / "competency_question" / f"{domain}_{task}_cqs.json"


def _load_source_cqs(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"CQ file must contain a JSON list: {path}")

    normalized_rows = []
    by_id = {}
    for index, cq in enumerate(data):
        if not isinstance(cq, dict):
            raise ValueError(f"CQ entry {index} must be an object: {path}")
        cq_id = cq.get("id")
        question = cq.get("value", cq.get("question"))
        if not isinstance(cq_id, str) or not cq_id.strip():
            raise ValueError(f"CQ entry {index} must have a non-empty string id: {path}")
        if not isinstance(question, str):
            raise ValueError(f"CQ {cq_id!r} must have a string value or question: {path}")
        if cq_id in by_id and by_id[cq_id] != question:
            raise ValueError(f"CQ id {cq_id!r} has conflicting questions: {path}")
        by_id[cq_id] = question
        normalized_rows.append({"id": cq_id, "value": question})
    return normalized_rows


def _read_cq_rows(path: Path) -> list[dict]:
    ordered = []
    seen = set()
    for cq in _load_source_cqs(path):
        if cq["id"] not in seen:
            seen.add(cq["id"])
            ordered.append(cq)
    return ordered


def _load_cqs(path: Path) -> list[dict]:
    return _read_cq_rows(path)


def _raw_count(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"CQ file must contain a JSON list: {path}")
    return len(data)


def _domain_slugs(project_root: Path) -> list[str]:
    slugs = set()
    for task, task_dir in _TASK_DIRS.items():
        cq_dir = project_root / task_dir / "competency_question"
        suffix = f"_{task}_cqs.json"
        if cq_dir.is_dir():
            slugs.update(path.name[: -len(suffix)] for path in cq_dir.glob(f"*{suffix}"))
    return sorted(slugs)


def list_domains(project_root: Path) -> list[dict]:
    domains = []
    for slug in _domain_slugs(project_root):
        counts = {}
        source_counts = {}
        deduplicated = {}
        for task in _TASK_DIRS:
            path = _cq_file(project_root, task, slug)
            if path.is_file():
                unique_count = len(_load_cqs(path))
                raw_count = _raw_count(path)
                counts[task] = unique_count
                source_counts[task] = raw_count
                deduplicated[task] = raw_count - unique_count
        domains.append(
            {
                "slug": slug,
                "name": slug.replace("_", " ").title(),
                "counts": counts,
                "source_counts": source_counts,
                "deduplicated_exact_duplicates": deduplicated,
            }
        )
    return domains


def get_domain_detail(project_root: Path, domain: str) -> dict:
    if domain not in _domain_slugs(project_root):
        raise KeyError(domain)

    tasks = {}
    for task in _TASK_DIRS:
        path = _cq_file(project_root, task, domain)
        if not path.is_file():
            continue
        cqs = _load_cqs(path)
        raw_count = _raw_count(path)
        tasks[task] = {
            "count": len(cqs),
            "source_count": raw_count,
            "raw_count": raw_count,
            "deduplicated_exact_duplicates": raw_count - len(cqs),
            "cqs": [
                {"id": cq["id"], "question": cq.get("value", cq.get("question"))}
                for cq in cqs
            ],
            "input_requirements": (
                {"class": "List of class term strings", "property": "List of property term strings"}
                if task == "cq2term"
                else {"review": "Review the complete CQ list before starting the run"}
            ),
        }
    return {"slug": domain, "name": domain.replace("_", " ").title(), "tasks": tasks}
