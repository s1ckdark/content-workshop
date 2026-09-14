import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from ui.job_dialog import JobDialog


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class FakeWorker(QObject):
    progress = Signal(str, int)
    log = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        pass

    def cancel(self) -> None:
        pass


@pytest.fixture
def dialog(qapp):
    worker = FakeWorker()
    d = JobDialog(worker, "테스트", None)
    yield d
    # The dialog's QThread keeps its own event loop running until quit();
    # make sure it never lingers past the test.
    d._thread.quit()
    d._thread.wait(2000)


def test_reject_is_ignored_while_job_running(dialog):
    dialog.reject()

    assert dialog._done is False
    assert dialog.result() is None


def test_reject_closes_once_job_is_done(dialog):
    dialog._on_finished({"path": "x"})
    assert dialog._done is True

    dialog.reject()
    # super().reject() ran; the dialog's own result() still reflects the job.
    assert dialog.result() == {"path": "x"}


def test_finished_log_summarizes_dict_result(dialog):
    dialog._on_finished({"name": "my template", "analyses": [{"huge": "data"}] * 50})

    log_text = dialog._log.toPlainText()
    assert "✓ 완료: my template" in log_text
    assert "huge" not in log_text


def test_finished_log_falls_back_to_dict_label(dialog):
    dialog._on_finished({"unrelated": 1})

    assert "✓ 완료: dict" in dialog._log.toPlainText()


def test_finished_log_keeps_non_dict_result(dialog):
    dialog._on_finished("https://example.test/video")

    assert "✓ 완료: https://example.test/video" in dialog._log.toPlainText()
