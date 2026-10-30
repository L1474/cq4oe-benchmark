import hashlib
import io
import json
import zipfile
from pathlib import Path

from web.domain.catalog import _cq_file, _load_cqs, _load_source_cqs


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


def build_cq_bundle(project_root: Path, task: str, domain: str) -> bytes:
    cqs = _load_cqs(_cq_file(project_root, task, domain))
    source_cqs = _load_source_cqs(_cq_file(project_root, task, domain))
    canonical_cq_json = json.dumps(
        source_cqs, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    manifest = {
        "task": task,
        "domain": domain,
        "version": hashlib.sha256(canonical_cq_json).hexdigest(),
        "count": len(cqs),
        "source_count": len(source_cqs),
        "deduplicated_exact_duplicates": len(source_cqs) - len(cqs),
        "expected_cq_ids": [cq["id"] for cq in cqs],
    }
    readme = (
        f"CQ4OE {task} questions for {domain}.\n"
        "Use the manifest to identify the task, domain, and required CQ IDs.\n"
    )
    files = {
        "cqs.json": _json_bytes(cqs),
        "manifest.json": _json_bytes(manifest),
        "README.txt": readme.encode("utf-8"),
    }
    if task == "cq2term":
        files["prediction_template.json"] = _json_bytes(
            [
                {"id": cq["id"], "value": cq.get("value", cq.get("question")), "class": [], "property": []}
                for cq in cqs
            ]
        )

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    return output.getvalue()
