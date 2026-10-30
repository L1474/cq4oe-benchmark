from pathlib import Path
import sys
import threading
import time
from unittest.mock import patch

import pytest

from web.services.evaluator import EvaluationStageError, run_stage
from web.types import EvaluationStage


class _Pipe:
    def __init__(self, chunks):
        self.chunks = iter(chunks)

    def readline(self):
        return next(self.chunks, "")


class _Process:
    def __init__(self, code=0):
        self.stdout = _Pipe(["out-1", "out-2"])
        self.stderr = _Pipe(["err-1"])
        self.code = code

    def wait(self):
        return self.code


@pytest.mark.parametrize("code", [0, 3])
def test_run_stage_streams_both_output_pipes_and_retains_logs(tmp_path, code):
    stage = EvaluationStage("class", ["python", "stage.py"], tmp_path)
    out_path, err_path = tmp_path / "class.stdout.log", tmp_path / "class.stderr.log"
    events = []
    with patch("web.services.evaluator.subprocess.Popen", return_value=_Process(code)):
        if code:
            with pytest.raises(EvaluationStageError) as error:
                run_stage(stage, out_path, err_path, events.append)
            assert error.value.exit_code == code
            assert error.value.stdout_path == out_path
        else:
            run_stage(stage, out_path, err_path, events.append)
    assert out_path.read_text(encoding="utf-8") == "out-1out-2"
    assert err_path.read_text(encoding="utf-8") == "err-1"
    assert {event["stream"] for event in events} == {"stdout", "stderr"}


def test_run_stage_delivers_output_before_child_exits(tmp_path):
    stage = EvaluationStage("stream", [sys.executable, "-u", "-c",
        "import time; print('ready', flush=True); time.sleep(0.8)"], tmp_path)
    out_path, err_path = tmp_path / "stream.stdout.log", tmp_path / "stream.stderr.log"
    delivered = threading.Event()
    finished = threading.Event()

    def event_sink(event):
        if event["stream"] == "stdout" and "ready" in event["text"]:
            delivered.set()

    def run():
        run_stage(stage, out_path, err_path, event_sink)
        finished.set()

    worker = threading.Thread(target=run)
    worker.start()
    try:
        assert delivered.wait(0.4), "stdout should be delivered while the child is still running"
        assert not finished.is_set()
    finally:
        worker.join(timeout=2)
    assert not worker.is_alive()
    assert out_path.read_text(encoding="utf-8").startswith("ready")


def test_run_stage_terminates_sleeping_child_and_retains_partial_log(tmp_path):
    from web.services.evaluator import EvaluationCancelled

    stage = EvaluationStage("sleep", [sys.executable, "-u", "-c",
        "import time; print('started', flush=True); time.sleep(60)"], tmp_path)
    stop = threading.Event()
    out_path, err_path = tmp_path / "sleep.stdout.log", tmp_path / "sleep.stderr.log"
    seen = threading.Event()
    errors = []

    def sink(event):
        if "started" in event.get("text", ""):
            seen.set()

    def run():
        try:
            run_stage(stage, out_path, err_path, sink, stop_event=stop)
        except EvaluationCancelled as exc:
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    try:
        assert seen.wait(5)
        stop.set()
        thread.join(3)
        assert not thread.is_alive()
        assert len(errors) == 1
        assert out_path.read_text(encoding="utf-8").startswith("started")
    finally:
        stop.set()
        thread.join(3)


def test_run_stage_passes_ollama_host_to_child(tmp_path):
    stage = EvaluationStage("env", [sys.executable, "-c",
        "import os; print(os.environ['OLLAMA_HOST'])"], tmp_path)
    out_path, err_path = tmp_path / "env.stdout.log", tmp_path / "env.stderr.log"
    run_stage(stage, out_path, err_path, lambda _: None,
              env={"OLLAMA_HOST": "http://ollama:11434"})
    assert out_path.read_text(encoding="utf-8").strip() == "http://ollama:11434"
