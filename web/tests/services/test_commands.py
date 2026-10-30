from pathlib import Path

from web.services.commands import build_cq2onto_commands, build_cq2term_command
from web.services.worker import LocalEvaluator
from web.types import RunItem, RunPaths


def _within(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def test_cq2term_command_uses_read_only_gold_and_item_workspace(tmp_path):
    repo = tmp_path / "repo"
    paths = RunPaths(tmp_path / "runs" / "run-1" / "items" / "item-1")
    paths.ensure()
    input_path = paths.input / "prediction.json"
    item = RunItem("item-1", "cq2term", "wine", input_path)

    command = build_cq2term_command(repo, item, paths, {})
    args = dict(zip(command[2::2], command[3::2]))

    assert command[1] == "scripts/eval_cq_terms.py"
    assert Path(args["--gold_cq_to_terms"]).resolve() == (
        repo / "CQ2Term/00_gold_standard/wine/cq_to_terms_wine.json"
    ).resolve()
    assert Path(args["--pred_cq_to_terms"]).resolve() == input_path.resolve()
    assert all(_within(Path(value), paths.root) for key, value in args.items()
               if key.startswith("--save_"))
    assert Path(args["--save_report_md"]).name == "report.md"
    assert Path(args["--save_cq_coverage_csv"]).exists() is False


def test_cq2onto_stages_are_ordered_and_outputs_stay_in_item_workspace(tmp_path):
    repo = tmp_path / "repo"
    paths = RunPaths(tmp_path / "runs" / "run-1" / "items" / "item-1")
    paths.ensure()
    input_path = paths.input / "submitted.owl"
    input_path.write_text("ontology", encoding="utf-8")
    item = RunItem("item-1", "cq2onto", "wine", input_path)

    stages = build_cq2onto_commands(repo, item, paths, {})

    assert [stage.name for stage in stages] == [
        "class", "property", "triple", "atomic", "axiom", "hierarchy"
    ]
    for stage in stages:
        assert stage.cwd == repo / "CQ2Onto"
        assert stage.command[1].startswith("scripts/")
        for index, value in enumerate(stage.command[:-1]):
            if value.startswith("--save_") or value.startswith("--output_"):
                assert _within(Path(stage.command[index + 1]), paths.root)
        if stage.name != "atomic":
            assert stage.report_path == paths.results / "report.md"
    atomic = stages[3]
    assert Path(atomic.command[-1]).is_relative_to(paths.work)
    assert not Path(atomic.command[-1]).is_relative_to(repo)
    assert "--pairs_csv" in stages[4].command
    assert "--output_txt" in stages[5].command


def test_axiom_stage_uses_configured_ollama_service_url(tmp_path):
    repo = tmp_path / "repo"
    paths = RunPaths(tmp_path / "runs" / "item")
    paths.ensure()
    input_path = paths.input / "submitted.owl"
    input_path.write_text("ontology", encoding="utf-8")
    item = RunItem("item", "cq2onto", "wine", input_path)
    stages = build_cq2onto_commands(repo, item, paths, {}, ollama_url="http://ollama:11434")
    axiom = next(stage for stage in stages if stage.name == "axiom")
    assert axiom.command[axiom.command.index("--ollama_url") + 1] == "http://ollama:11434"


def test_local_evaluator_routes_all_embedding_stages_to_ollama_service(tmp_path, monkeypatch):
    seen = []

    def capture(stage, stdout_path, stderr_path, event_sink, **kwargs):
        seen.append((stage.name, stage.command, kwargs["env"]))

    monkeypatch.setattr("web.services.worker.run_stage", capture)
    monkeypatch.setattr("web.services.worker.extract_cq2term_metrics", lambda *_: [])
    monkeypatch.setattr("web.services.worker.extract_cq2onto_metrics", lambda *_: [])
    evaluator = LocalEvaluator(tmp_path, "http://ollama:11434")
    for task, filename in (("cq2term", "prediction.json"), ("cq2onto", "submitted.owl")):
        item_root = tmp_path / "runs" / task / "items" / "item"
        input_path = item_root / "input" / filename
        input_path.parent.mkdir(parents=True)
        input_path.write_text("{}", encoding="utf-8")
        evaluator.evaluate_item({"run_path": str(item_root.parents[1]), "config_json": "{}"},
                                {"id": "item", "task": task, "domain": "wine", "input_path": str(input_path)},
                                lambda _: None)

    assert {name for name, _, _ in seen} >= {"evaluate", "class", "property", "triple", "axiom"}
    for name, _, env in seen:
        if name in {"evaluate", "class", "property", "triple", "axiom"}:
            assert env["OLLAMA_HOST"] == "http://ollama:11434"
    axiom_command = next(command for name, command, _ in seen if name == "axiom")
    assert axiom_command[axiom_command.index("--ollama_url") + 1] == "http://ollama:11434"
