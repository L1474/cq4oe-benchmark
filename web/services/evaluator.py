import os
import queue
import signal
import subprocess
import threading
from pathlib import Path
from typing import Callable

from web.types import EvaluationStage


class EvaluationStageError(RuntimeError):
    def __init__(self, stage: str, exit_code: int, stdout_path: Path, stderr_path: Path):
        self.stage = stage
        self.exit_code = exit_code
        self.stdout_path = Path(stdout_path)
        self.stderr_path = Path(stderr_path)
        super().__init__(f"evaluation stage {stage!r} exited with {exit_code}; "
                         f"stdout: {stdout_path}; stderr: {stderr_path}")


class EvaluationCancelled(RuntimeError):
    pass


def _stop_process(process):
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        pass
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        process.kill()
    process.wait()


def run_stage(stage: EvaluationStage, stdout_path: Path, stderr_path: Path,
              event_sink: Callable, *, stop_event: threading.Event | None = None,
              env: dict[str, str] | None = None) -> None:
    if stop_event and stop_event.is_set():
        raise EvaluationCancelled(f"evaluation stage {stage.name!r} cancelled before launch")
    stdout_path, stderr_path = Path(stdout_path), Path(stderr_path)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [str(part) for part in stage.command], cwd=stage.cwd,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
        env={**os.environ, **env} if env else None,
        start_new_session=os.name == "posix",
    )
    chunks: queue.Queue = queue.Queue()
    sentinel = object()

    def read_pipe(name: str, pipe) -> None:
        try:
            while True:
                chunk = pipe.readline()
                if not chunk:
                    break
                chunks.put((name, chunk))
        finally:
            chunks.put((name, sentinel))

    threads = [
        threading.Thread(target=read_pipe, args=("stdout", process.stdout), daemon=True),
        threading.Thread(target=read_pipe, args=("stderr", process.stderr), daemon=True),
    ]
    for thread in threads:
        thread.start()
    ended = set()
    cancelled = False
    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open("w", encoding="utf-8") as stderr_file:
        streams = {"stdout": stdout_file, "stderr": stderr_file}
        while len(ended) < 2:
            if stop_event and stop_event.is_set() and not cancelled:
                cancelled = True
                _stop_process(process)
            try:
                name, chunk = chunks.get(timeout=0.1)
            except queue.Empty:
                continue
            if chunk is sentinel:
                ended.add(name)
                continue
            streams[name].write(chunk)
            streams[name].flush()
            event_sink({"stage": stage.name, "stream": name, "text": chunk})
    for thread in threads:
        thread.join()
    return_code = process.wait()
    if cancelled:
        raise EvaluationCancelled(f"evaluation stage {stage.name!r} was interrupted")
    if return_code:
        raise EvaluationStageError(stage.name, return_code, stdout_path, stderr_path)
