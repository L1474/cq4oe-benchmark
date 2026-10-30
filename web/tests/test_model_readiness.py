import json
import threading

from web.services.model_readiness import ModelReadinessService


def test_readiness_pulls_embeddinggemma_and_sets_ready_only_after_tags_report_it():
    service = ModelReadinessService(retry_interval=0.01)
    calls = []
    pulled = threading.Event()

    def request(path, body=None):
        calls.append((path, body))
        if path == "/api/pull":
            pulled.set()
            return b"{}"
        if pulled.is_set():
            return json.dumps({"models": [{"name": "embeddinggemma:latest"}]}).encode()
        return b'{"models":[]}'

    service._request = request
    service.start()
    try:
        assert service._ready.wait(1)
        assert service.is_ready()
        assert ("/api/pull", {"name": "embeddinggemma", "stream": False}) in calls
    finally:
        service.stop(1)
