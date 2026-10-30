from pathlib import Path
from unittest.mock import patch

import pytest

from web.services.evaluator import EvaluationStageError, run_stage
from web.types import EvaluationStage


class _Pipe:
    def __init__(self, chunks):
        self.chunks = iter(chunks)

    def read(self, _size):
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
