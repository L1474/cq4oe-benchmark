import hashlib
import io
import json
import shutil
import zipfile

from web.domain.bundles import build_cq_bundle


PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parents[3]


def _read_bundle(task, domain):
    with zipfile.ZipFile(io.BytesIO(build_cq_bundle(PROJECT_ROOT, task, domain))) as archive:
        return archive.testzip(), {name: archive.read(name) for name in archive.namelist()}


def test_cq2term_bundle_contains_source_manifest_readme_and_blank_template():
    corrupt_file, files = _read_bundle("cq2term", "wine")

    assert set(files) == {"cqs.json", "manifest.json", "README.txt", "prediction_template.json"}
    source = json.loads(files["cqs.json"])
    manifest = json.loads(files["manifest.json"])
    template = json.loads(files["prediction_template.json"])
    canonical = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    assert manifest == {
        "task": "cq2term",
        "domain": "wine",
        "version": hashlib.sha256(canonical).hexdigest(),
        "count": 5,
        "source_count": 5,
        "deduplicated_exact_duplicates": 0,
        "expected_cq_ids": [cq["id"] for cq in source],
    }
    assert all(set(row) == {"id", "value", "class", "property"} for row in template)
    assert all(row["class"] == row["property"] == [] for row in template)
    assert corrupt_file is None


def test_bundles_omit_gold_paths_and_answers():
    for task in ("cq2term", "cq2onto"):
        _, files = _read_bundle(task, "wine")
        expected = {"cqs.json", "manifest.json", "README.txt"}
        if task == "cq2term":
            expected.add("prediction_template.json")
        assert set(files) == expected
        for name, payload in files.items():
            assert "gold" not in name.lower()
            assert b"gold" not in payload.lower()
            assert b"answer" not in payload.lower()


def test_bundle_bytes_are_deterministic():
    assert build_cq_bundle(PROJECT_ROOT, "cq2term", "wine") == build_cq_bundle(
        PROJECT_ROOT, "cq2term", "wine"
    )


def test_odrl_package_exposes_raw_and_deduplicated_counts():
    _, files = _read_bundle("cq2term", "odrl")
    manifest = json.loads(files["manifest.json"])
    template = json.loads(files["prediction_template.json"])

    assert manifest["source_count"] == 19
    assert manifest["count"] == 17
    assert manifest["deduplicated_exact_duplicates"] == 2
    assert len(manifest["expected_cq_ids"]) == len(template) == 17


def test_manifest_version_hashes_canonical_raw_source_json(tmp_path):
    root = tmp_path
    source_path = root / "CQ2Term" / "competency_question" / "wine_cq2term_cqs.json"
    source_path.parent.mkdir(parents=True)
    shutil.copy(PROJECT_ROOT / "CQ2Term/competency_question/wine_cq2term_cqs.json", source_path)

    first = build_cq_bundle(root, "cq2term", "wine")
    repeated = build_cq_bundle(root, "cq2term", "wine")
    with zipfile.ZipFile(io.BytesIO(first)) as archive:
        first_manifest = json.loads(archive.read("manifest.json"))
        first_cqs = archive.read("cqs.json")
    with zipfile.ZipFile(io.BytesIO(repeated)) as archive:
        repeated_manifest = json.loads(archive.read("manifest.json"))

    source = json.loads(source_path.read_text(encoding="utf-8"))
    source[0]["provenance"] = "changed source-only field"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    changed = build_cq_bundle(root, "cq2term", "wine")
    with zipfile.ZipFile(io.BytesIO(changed)) as archive:
        changed_manifest = json.loads(archive.read("manifest.json"))
        changed_cqs = archive.read("cqs.json")

    assert first == repeated
    assert repeated_manifest["version"] == first_manifest["version"]
    assert changed_cqs == first_cqs
    assert changed_manifest["version"] != first_manifest["version"]
