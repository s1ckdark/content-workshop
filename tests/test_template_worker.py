import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

import ui.workers as workers
from ui.workers import TemplateWorker


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _connect(worker):
    signals = {"progress": [], "log": [], "finished": [], "failed": []}
    worker.progress.connect(lambda phase, pct: signals["progress"].append((phase, pct)))
    worker.log.connect(signals["log"].append)
    worker.finished.connect(signals["finished"].append)
    worker.failed.connect(signals["failed"].append)
    return signals


def test_run_fails_immediately_without_api_key(qapp, monkeypatch):
    monkeypatch.setattr(workers, "get_openrouter_api_key", lambda: "")
    worker = TemplateWorker(["https://www.youtube.com/watch?v=AAAAAAAAAAA"], "name")
    signals = _connect(worker)

    worker.run()

    assert len(signals["failed"]) == 1
    assert "API 키" in signals["failed"][0]
    assert signals["finished"] == []


def test_run_skips_failed_url_and_finishes(qapp, monkeypatch):
    monkeypatch.setattr(workers, "get_openrouter_api_key", lambda: "test-key")

    def fake_analyze(url):
        if url == "bad":
            raise RuntimeError("private video")
        return {"url": url, "topic": "t", "hook_type": "h", "sentence_count": 5, "tone": "fast"}

    monkeypatch.setattr(workers, "analyze", fake_analyze)
    monkeypatch.setattr(workers, "synthesize", lambda analyses, name: {"name": name, "count": len(analyses)})

    worker = TemplateWorker(["good", "bad"], "name")
    signals = _connect(worker)

    worker.run()

    assert signals["failed"] == []
    assert len(signals["finished"]) == 1
    assert signals["finished"][0] == {"name": "name", "count": 1}
    assert any(line.startswith("건너뜀:") and "bad" in line and "private video" in line for line in signals["log"])


def test_run_reports_cancel(qapp, monkeypatch):
    monkeypatch.setattr(workers, "get_openrouter_api_key", lambda: "test-key")
    monkeypatch.setattr(workers, "analyze", lambda url: {"url": url})

    def fake_synthesize(analyses, name):
        return {"name": name, "count": len(analyses)}

    monkeypatch.setattr(workers, "synthesize", fake_synthesize)

    worker = TemplateWorker(["good"], "name")
    signals = _connect(worker)
    worker.cancel()

    worker.run()

    assert signals["finished"] == []
    assert signals["failed"] == ["사용자가 취소했습니다."]
