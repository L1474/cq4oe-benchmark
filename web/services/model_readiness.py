import json
import threading
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


class ModelReadinessService:
    def __init__(self, ollama_url="http://127.0.0.1:11434", model="embeddinggemma", retry_interval=5):
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model
        self.retry_interval = retry_interval
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        self.error = None

    def is_ready(self) -> bool:
        return self._ready.is_set()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._check_loop, name="ollama-readiness", daemon=True)
        self._thread.start()

    def stop(self, timeout=None) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)

    def _request(self, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = Request(self.ollama_url + path, data=data,
                          headers={"Content-Type": "application/json"} if data is not None else {})
        with urlopen(request, timeout=10) as response:
            return response.read()

    def _check_loop(self):
        while not self._stop.is_set():
            try:
                tags = json.loads(self._request("/api/tags"))
                models = {entry.get("name", "").split(":")[0] for entry in tags.get("models", [])}
                if self.model not in models:
                    self._request("/api/pull", {"name": self.model, "stream": False})
                    tags = json.loads(self._request("/api/tags"))
                    models = {entry.get("name", "").split(":")[0] for entry in tags.get("models", [])}
                if self.model in models:
                    self.error = None
                    self._ready.set()
                    return
                self.error = f"Ollama did not report {self.model} after pull."
            except (URLError, TimeoutError, ValueError, OSError) as exc:
                self.error = str(exc)
            self._stop.wait(self.retry_interval)
