"""
Modal job dialog — owns a QThread, drives a worker, renders progress + log.
The worker is any QObject exposing:
    progress(str, int), log(str), finished(object), failed(str)
and a `cancel()` method (optional).
"""

from typing import Optional

from PySide6.QtCore import QObject, Qt, QThread, Slot
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class JobDialog(QDialog):
    def __init__(self, worker: QObject, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(620, 380)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self._worker = worker
        self._thread = QThread(self)
        worker.moveToThread(self._thread)
        self._thread.started.connect(worker.run)

        self._phase = QLabel("대기 중...")
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)

        self._cancel_btn = QPushButton("취소")
        self._close_btn = QPushButton("닫기")
        self._close_btn.setEnabled(False)

        bb = QDialogButtonBox()
        bb.addButton(self._cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        bb.addButton(self._close_btn, QDialogButtonBox.ButtonRole.AcceptRole)

        layout = QVBoxLayout(self)
        layout.addWidget(self._phase)
        layout.addWidget(self._bar)
        layout.addWidget(self._log, 1)
        layout.addWidget(bb)

        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        self._close_btn.clicked.connect(self.accept)

        worker.progress.connect(self._on_progress)
        worker.log.connect(self._append_log)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)

        self._result: Optional[object] = None
        self._done = False

        self._thread.start()

    # --------------------------------------------------------------- slots
    @Slot(str, int)
    def _on_progress(self, phase: str, pct: int) -> None:
        self._phase.setText(phase)
        self._bar.setValue(pct)
        self._append_log(f"[{pct:3d}%] {phase}")

    @Slot(str)
    def _append_log(self, line: str) -> None:
        self._log.appendPlainText(line)

    @Slot(object)
    def _on_finished(self, result: object) -> None:
        self._append_log(f"✓ 완료: {self._summarize(result)}")
        self._result = result
        self._mark_done()

    @staticmethod
    def _summarize(result: object) -> object:
        # A dict result (e.g. a template with its full `analyses`) can be
        # large; log a short identifier instead of dumping the whole thing.
        if isinstance(result, dict):
            for key in ("name", "title", "path"):
                if result.get(key):
                    return result[key]
            return "dict"
        return result

    @Slot(str)
    def _on_failed(self, msg: str) -> None:
        self._append_log(f"✗ 실패: {msg}")
        self._mark_done()

    def _on_cancel_clicked(self) -> None:
        if hasattr(self._worker, "cancel"):
            self._worker.cancel()
        self._cancel_btn.setEnabled(False)
        self._append_log("⏸ 취소 요청. 현재 단계가 끝나면 중단됩니다.")

    # --------------------------------------------------------------- helpers
    def _mark_done(self) -> None:
        self._done = True
        self._cancel_btn.setEnabled(False)
        self._close_btn.setEnabled(True)
        self._thread.quit()

    def result(self) -> Optional[object]:
        return self._result

    def closeEvent(self, event) -> None:  # type: ignore[override]
        # Block window close while job is still running so we don't orphan
        # the Chromium process the worker owns.
        if not self._done:
            event.ignore()
            return
        self._thread.wait(2000)
        super().closeEvent(event)

    def reject(self) -> None:  # type: ignore[override]
        # QDialog.reject() (triggered by Esc) bypasses closeEvent, so it
        # would close a still-running job. Ignore it until the job is done.
        if not self._done:
            return
        super().reject()
