import hashlib
import io
import json
import zipfile
from pathlib import Path

from web.domain.catalog import _cq_file, _load_cqs


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


def build_cq_bundle(project_root: Path, task: str, domain: str) -> bytes:
    cq_path = _cq_file(project_root, task, domain)
    raw_source_cqs = json.loads(cq_path.read_text(encoding="utf-8"))
    cqs = _load_cqs(cq_path)
    canonical_cq_json = json.dumps(
        raw_source_cqs, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    manifest = {
        "task": task,
        "domain": domain,
        "version": hashlib.sha256(canonical_cq_json).hexdigest(),
        "count": len(cqs),
        "source_count": len(raw_source_cqs),
        "deduplicated_exact_duplicates": len(raw_source_cqs) - len(cqs),
        "expected_cq_ids": [cq["id"] for cq in cqs],
    }
    readme = (
        f"CQ4OE {domain} 领域 {task} 能力问题包\n\n"
        "cqs.json 是需要交给外部生成程序的完整 CQ 清单；manifest.json 列出必需的 CQ ID 和版本。\n"
        + (
            "填写 prediction_template.json 中每个 CQ 的 class/property 字符串数组，最终上传一个 UTF-8 JSON 文件。\n"
            if task == "cq2term" else
            "将全部 CQ 提供给你的 normal、cqbycq 或 agent 方法，最终生成一个合并的本体文件。\n"
            "上传 .owl/.rdf/.xml（RDF/XML）或 .ttl/.nt/.n3 文件；生成日志不必上传。\n"
        )
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
