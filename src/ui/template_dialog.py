"""
Format-template dialogs: reference URL input → analysis job → review/edit → save.
"""

from typing import List, Optional, Tuple

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from classes.ReferenceAnalyzer import parse_url_lines
from prompts import HEX_COLOR
from templates import (
    SENTENCE_COUNT_MAX,
    SENTENCE_COUNT_MIN,
    add_template,
    get_template,
    update_template,
)
from ui.job_dialog import JobDialog
from ui.workers import TemplateWorker

MAX_REFERENCE_URLS = 10


def _lines(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


class TemplateInputDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("포맷 템플릿 — 레퍼런스 입력")
        self.setMinimumWidth(560)

        self._name = QLineEdit()
        self._name.setPlaceholderText("예: 생활 속 돈 습관")
        self._urls = QPlainTextEdit()
        self._urls.setPlaceholderText(
            "좋다고 생각한 쇼츠 URL을 한 줄에 하나씩 (1~10개)\nhttps://www.youtube.com/shorts/..."
        )

        form = QFormLayout()
        form.addRow("템플릿 이름", self._name)
        form.addRow("레퍼런스 URL", self._urls)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("공개 영상만 분석할 수 있습니다. 영상은 다운로드하지 않습니다."))
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._values: Tuple[str, List[str]] = ("", [])

    def _on_accept(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "필수 입력", "템플릿 이름을 입력해 주세요.")
            return

        valid, invalid = parse_url_lines(self._urls.toPlainText())
        if invalid:
            QMessageBox.warning(
                self, "잘못된 URL", "YouTube 영상 URL이 아닌 줄이 있습니다:\n" + "\n".join(invalid)
            )
            return
        if not valid:
            QMessageBox.warning(self, "필수 입력", "레퍼런스 URL을 1개 이상 입력해 주세요.")
            return
        if len(valid) > MAX_REFERENCE_URLS:
            QMessageBox.warning(
                self, "URL 개수 초과", f"레퍼런스 URL은 최대 {MAX_REFERENCE_URLS}개까지 입력할 수 있습니다."
            )
            return

        self._values = (name, valid)
        self.accept()

    def values(self) -> Tuple[str, List[str]]:
        return self._values


class TemplateReviewDialog(QDialog):
    def __init__(self, template: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"포맷 템플릿 검토 — {template.get('name', '')}")
        self.setMinimumSize(640, 720)
        self._template = template

        self._name = QLineEdit(template.get("name", ""))
        self._niche = QLineEdit(template.get("niche", ""))
        self._language = QLineEdit(template.get("language", ""))
        self._topic_angle = QPlainTextEdit(template.get("topic_angle", ""))
        self._hook_pattern = QPlainTextEdit(template.get("hook_pattern", ""))
        self._tone = QPlainTextEdit(template.get("tone", ""))
        self._visual_style = QPlainTextEdit(template.get("visual_style", ""))
        self._sentence_count = QSpinBox()
        self._sentence_count.setRange(SENTENCE_COUNT_MIN, SENTENCE_COUNT_MAX)
        self._sentence_count.setValue(int(template.get("sentence_count", SENTENCE_COUNT_MIN)))
        self._subtitle_color = QLineEdit(template.get("subtitle_color", ""))
        self._example_topics = QPlainTextEdit("\n".join(template.get("example_topics", [])))
        self._avoid = QPlainTextEdit("\n".join(template.get("avoid", [])))

        for editor in (self._topic_angle, self._hook_pattern, self._tone, self._visual_style):
            editor.setFixedHeight(60)

        sources = QLabel("\n".join(template.get("source_urls", [])))
        sources.setWordWrap(True)

        form = QFormLayout()
        form.addRow("이름", self._name)
        form.addRow("니치", self._niche)
        form.addRow("언어", self._language)
        form.addRow("주제 각도", self._topic_angle)
        form.addRow("훅 패턴", self._hook_pattern)
        form.addRow("말투", self._tone)
        form.addRow("비주얼 스타일", self._visual_style)
        form.addRow("문장 수", self._sentence_count)
        form.addRow("자막 색 (#RRGGBB)", self._subtitle_color)
        form.addRow("예시 주제 (줄 단위)", self._example_topics)
        form.addRow("금지 목록 (줄 단위)", self._avoid)
        form.addRow("레퍼런스", sources)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._result: Optional[dict] = None

    def _on_accept(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "필수 입력", "템플릿 이름을 입력해 주세요.")
            return
        color = self._subtitle_color.text().strip()
        if not HEX_COLOR.match(color):
            QMessageBox.warning(self, "자막 색", "자막 색은 #RRGGBB 형식이어야 합니다.")
            return

        result = dict(self._template)
        result.update(
            {
                "name": name,
                "niche": self._niche.text().strip(),
                "language": self._language.text().strip().lower(),
                "topic_angle": self._topic_angle.toPlainText().strip(),
                "hook_pattern": self._hook_pattern.toPlainText().strip(),
                "tone": self._tone.toPlainText().strip(),
                "visual_style": self._visual_style.toPlainText().strip(),
                "sentence_count": self._sentence_count.value(),
                "subtitle_color": color.upper(),
                "example_topics": _lines(self._example_topics.toPlainText()),
                "avoid": _lines(self._avoid.toPlainText()),
            }
        )
        self._result = result
        self.accept()

    def result_template(self) -> Optional[dict]:
        return self._result


def add_template_flow(parent: QWidget) -> bool:
    input_dialog = TemplateInputDialog(parent)
    if input_dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    name, urls = input_dialog.values()

    job = JobDialog(TemplateWorker(urls, name), f"템플릿 분석 — {name}", parent)
    job.exec()
    template = job.result()
    if not isinstance(template, dict):
        return False

    review = TemplateReviewDialog(template, parent)
    if review.exec() != QDialog.DialogCode.Accepted:
        return False
    add_template(review.result_template())
    return True


def edit_template_flow(parent: QWidget, row: dict) -> bool:
    template = get_template(row.get("id", ""))
    if template is None:
        QMessageBox.warning(parent, "템플릿 없음", "템플릿을 찾을 수 없습니다. 새로고침해 주세요.")
        return False

    review = TemplateReviewDialog(template, parent)
    if review.exec() != QDialog.DialogCode.Accepted:
        return False
    update_template(review.result_template())
    return True
