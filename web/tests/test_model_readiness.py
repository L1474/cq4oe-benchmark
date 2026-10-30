import json
import threading
import time

from web.services.model_readiness import ModelReadinessService


def test_readiness_pulls_embeddinggemma_and_sets_ready_only_after_tags_report_it():
    service = ModelReadinessService(retry_interval=0.01)
    calls = []
    pulled = threading.Event()

    def request(path, body=None):
        calls.append((path, body))
        if pulled.is_set():
            return json.dumps({"models": [{"name": "embeddinggemma:latest"}]}).encode()
        return b'{"models":[]}'

    service._request = request
    service._pull_model = pulled.set
    service.start()
    try:
        assert service._ready.wait(1)
        assert service.is_ready()
        assert calls.count(("/api/tags", None)) >= 2
    finally:
        service.stop(1)


def test_readiness_waits_for_a_slow_model_pull():
    service = ModelReadinessService(retry_interval=0.01)
    pulled = threading.Event()
    pull_started = threading.Event()
    calls = []

    def request(path, body=None):
        calls.append((path, body))
        if pulled.is_set():
            return b'{"models":[{"name":"embeddinggemma:latest"}]}'
        return b'{"models":[]}'

    def slow_pull():
        pull_started.set()
        time.sleep(0.15)
        pulled.set()

    service._request = request
    service._pull_model = slow_pull
    service.start()
    try:
        assert service._ready.wait(1)
        assert service.is_ready()
        assert pull_started.is_set()
    finally:
        service.stop(1)


def test_pull_uses_streaming_response_and_unbounded_read_timeout(monkeypatch):
    service = ModelReadinessService()
    captured = {}

    class Socket:
        def settimeout(self, value):
            captured["read_timeout"] = value

    class Raw:
        _sock = Socket()

    class Body:
        raw = Raw()

    class Response:
        fp = Body()
        closed = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

        def __iter__(self):
            time.sleep(0.02)
            yield b'{"status":"downloading"}'

        def close(self):
            self.closed = True

    response = Response()

    def open_url(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        captured["connect_timeout"] = timeout
        return response

    monkeypatch.setattr("web.services.model_readiness.urlopen", open_url)
    service._pull_model()
    assert captured["url"].endswith("/api/pull")
    assert captured["body"] == {"name": "embeddinggemma", "stream": True}
    assert captured["connect_timeout"] == 10 and captured["read_timeout"] is None
    assert response.closed


def test_stop_closes_an_active_streaming_pull(monkeypatch):
    service = ModelReadinessService()
    entered = threading.Event()

    class Socket:
        def settimeout(self, value):
            pass

    class Raw:
        _sock = Socket()

    class Body:
        raw = Raw()

    class Response:
        fp = Body()

        def __init__(self):
            self.closed = threading.Event()

        def __iter__(self):
            entered.set()
            while not self.closed.is_set():
                time.sleep(0.01)
                yield b'{"status":"downloading"}'

        def close(self):
            self.closed.set()

    response = Response()
    monkeypatch.setattr("web.services.model_readiness.urlopen", lambda request, timeout: response)
    thread = threading.Thread(target=service._pull_model)
    thread.start()
    assert entered.wait(1)
    service.stop(1)
    thread.join(1)
    assert response.closed.is_set() and not thread.is_alive()
