import shutil
import sys
from pathlib import Path

from web.types import EvaluationStage, RunItem, RunPaths


_CQ2TERM_ARTIFACTS = {
    "--save_class_alignment_csv": "06_cq_terms/class_alignment.csv",
    "--save_property_alignment_csv": "06_cq_terms/property_alignment.csv",
    "--save_class_best_matching_csv": "06_cq_terms/class_best_matching.csv",
    "--save_property_best_matching_csv": "06_cq_terms/property_best_matching.csv",
    "--save_cq_coverage_csv": "06_cq_terms/cq_coverage.csv",
    "--save_term_coverage_csv": "06_cq_terms/term_coverage.csv",
    "--save_result_json": "06_cq_terms/result.json",
}


def _pair_args(values: dict) -> list[str]:
    return [part for key, value in values.items() for part in (key, str(value))]


def _require_within(path: Path, root: Path, label: str) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(Path(root).resolve()):
        raise ValueError(f"{label} must be inside the run item workspace")
    return resolved


def _gold_owl(project_root: Path, domain: str) -> Path:
    return project_root / "CQ2Onto" / "00_gold_standard" / domain / "ontology" / f"sub_{domain}.owl"


def _gold_axioms(project_root: Path, domain: str) -> Path:
    return project_root / "CQ2Onto" / "00_gold_standard" / domain / "axioms" / f"{domain}_axiom_gold.json"


def build_cq2term_command(project_root: Path, item: RunItem, paths: RunPaths,
                          config: dict) -> list[str]:
    paths.ensure()
    result_dir = paths.results / "06_cq_terms"
    result_dir.mkdir(parents=True, exist_ok=True)
    gold = project_root / "CQ2Term" / "00_gold_standard" / item.domain / f"cq_to_terms_{item.domain}.json"
    outputs = {flag: result_dir / relative.split("/", 1)[1]
               for flag, relative in _CQ2TERM_ARTIFACTS.items()}
    report = paths.results / "report.md"
    input_path = _require_within(item.input_path, paths.input, "prediction")
    return [
        sys.executable, "scripts/eval_cq_terms.py",
        "--gold_cq_to_terms", str(gold.resolve()),
        "--pred_cq_to_terms", str(input_path),
        *_pair_args(outputs),
        "--save_report_md", str(report.resolve()),
        "--cq_coverage_mode", str(config.get("cq_coverage_mode", "cq_local")),
        "--semantic_model", str(config.get("embedding_model", "embeddinggemma:latest")),
    ]


def build_cq2onto_commands(project_root: Path, item: RunItem, paths: RunPaths,
                           config: dict, *, ollama_url: str = "http://127.0.0.1:11434") -> list[EvaluationStage]:
    paths.ensure()
    task_root = (project_root / "CQ2Onto").resolve()
    domain = item.domain
    atomic_dir = paths.work / "atomic"
    atomic_dir.mkdir(parents=True, exist_ok=True)
    submitted = _require_within(Path(item.input_path).resolve(strict=True), paths.input, "uploaded ontology")
    isolated_ontology = atomic_dir / submitted.name
    if submitted != isolated_ontology.resolve():
        shutil.copy2(submitted, isolated_ontology)
    pred = isolated_ontology.resolve()
    gold_owl = _gold_owl(project_root, domain).resolve()
    gold_axioms = _gold_axioms(project_root, domain).resolve()
    report = (paths.results / "report.md").resolve()

    class_dir = paths.results / "01_class"
    property_dir = paths.results / "02_property"
    triple_dir = paths.results / "03_triple"
    axiom_dir = paths.results / "04_axiom"
    hierarchy_dir = paths.results / "05_hierarchy"
    for directory in (class_dir, property_dir, triple_dir, atomic_dir, axiom_dir, hierarchy_dir):
        directory.mkdir(parents=True, exist_ok=True)

    class_csv = class_dir / "class_best_matching.csv"
    property_csv = property_dir / "property_best_matching.csv"
    class_json = class_dir / "class_result.json"
    property_json = property_dir / "property_result.json"
    triple_json = triple_dir / "triple_result.json"
    atomic_json = atomic_dir / f"{pred.stem}_atomic_tbox.json"
    strict_cq_csv = axiom_dir / "strict_cq_coverage.csv"
    axiom_json = axiom_dir / "eval_axioms_result.json"
    hierarchy_json = hierarchy_dir / "hierarchy_result.json"
    methods = str(config.get("methods", "hard_match,sequence_match,levenshtein,jaro_winkler,semantic"))
    model = str(config.get("embedding_model", "embeddinggemma"))
    threshold_args = ["--hard_threshold", "1.0", "--lexical_threshold", "0.8", "--semantic_threshold", "0.6"]

    stages = [
        EvaluationStage("class", [sys.executable, "scripts/concept/eval_concept.py",
            "--generate_onto_file_path", str(pred), "--ground_onto_file_path", str(gold_owl),
            "--model_id", model, "--methods", methods, "--top_n", str(config.get("top_n", 3)),
            "--final_threshold", str(config.get("class_final_threshold", 0.6)), *threshold_args,
            "--save_file_path", str(class_json.resolve()), "--save_best_matching_csv", str(class_csv.resolve()),
            "--save_alignment_trace_csv", str((class_dir / "alignment_trace.csv").resolve()),
            "--save_alignment_trace_json", str((class_dir / "alignment_trace.json").resolve()),
            "--save_report_md", str(report)], task_root, class_json, report),
        EvaluationStage("property", [sys.executable, "scripts/property/eval_property.py",
            "--pred_onto", str(pred), "--gold_onto", str(gold_owl), "--model_id", model,
            "--methods", methods, "--top_n", str(config.get("top_n", 3)),
            "--final_threshold", str(config.get("property_final_threshold", 0.7)), *threshold_args,
            "--save_result", str(property_json.resolve()), "--save_best_matching_csv", str(property_csv.resolve()),
            "--save_alignment_trace_csv", str((property_dir / "alignment_trace.csv").resolve()),
            "--save_alignment_trace_json", str((property_dir / "alignment_trace.json").resolve()),
            "--save_report_md", str(report)], task_root, property_json, report),
        EvaluationStage("triple", [sys.executable, "scripts/triple/eval_triple.py",
            "--pred_onto", str(pred), "--gold_onto", str(gold_owl), "--class_csv", str(class_csv.resolve()),
            "--property_csv", str(property_csv.resolve()), "--model_id", model,
            "--save_result", str(triple_json.resolve()), "--save_layer3_csv", str((triple_dir / "layer3_pairs.csv").resolve()),
            "--save_layer3_json", str((triple_dir / "layer3_pairs.json").resolve()), "--save_report_md", str(report),
            "--literal_relax", "no"], task_root, triple_json, report),
        EvaluationStage("atomic", [sys.executable, "scripts/axioms/Axioms_atomic.py", str(pred)], task_root,
            atomic_json, None),
        EvaluationStage("axiom", [sys.executable, "scripts/axioms/eval_axioms.py",
            "--gold", str(gold_axioms), "--pred", str(atomic_json.resolve()),
            "--class_csv", str(class_csv.resolve()), "--property_csv", str(property_csv.resolve()),
            "--save_result_json", str(axiom_json.resolve()), "--details_csv", str((axiom_dir / "details.csv").resolve()),
            "--pairs_csv", str((axiom_dir / "layer2_pairs.csv").resolve()),
            "--cache_path", str((paths.work / "embedding_cache.json").resolve()),
            "--model", model,
            "--ollama_url", ollama_url,
            "--save_cq_csv", str(strict_cq_csv.resolve()), "--save_report_md", str(report),
            "--literal_relax", "no"], task_root, axiom_json, report),
        EvaluationStage("hierarchy", [sys.executable, "scripts/hierarchy/eval_hierarchy.py",
            "--gold_owl", str(gold_owl), "--pred_owl", str(pred),
            "--class_csv", str(class_csv.resolve()), "--property_csv", str(property_csv.resolve()),
            "--gold", str(gold_axioms), "--pred", str(atomic_json.resolve()),
            "--strict_cq_csv", str(strict_cq_csv.resolve()),
            "--output_json", str(hierarchy_json.resolve()),
            "--output_csv", str((hierarchy_dir / "hierarchy_pairs.csv").resolve()),
            "--output_md", str(report), "--output_txt", str((hierarchy_dir / "hierarchy_report.txt").resolve())],
            task_root, hierarchy_json, report),
    ]
    return stages
