"""
Add-item dialog. Renders one input row per FieldSpec. Returns a dict matching
the platform's field keys, with a fresh UUID injected as `id`.
"""

from uuid import uuid4

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.platforms import Platform


class AccountDialog(QDialog):
    def __init__(self, platform: Platform, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{platform.label} — 새 {platform.item_label}")
        self._platform = platform
        self._inputs: dict[str, QLineEdit] = {}

        form = QFormLayout()
        for spec in platform.fields:
            line = QLineEdit()
            line.setPlaceholderText(spec.placeholder)

            if spec.kind == "path":
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                browse = QPushButton("찾아보기...")
                browse.clicked.connect(lambda _=False, le=line: self._pick_directory(le))
                row_layout.addWidget(line)
                row_layout.addWidget(browse)
                form.addRow(spec.label, row)
            else:
                form.addRow(spec.label, line)

            self._inputs[spec.key] = line

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._payload: dict | None = None

    @staticmethod
    def _pick_directory(line: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(line, "프로필 디렉토리 선택")
        if path:
            line.setText(path)

    def _on_accept(self) -> None:
        payload: dict = {"id": str(uuid4())}

        for spec in self._platform.fields:
            value = self._inputs[spec.key].text().strip()
            if spec.required and not value:
                QMessageBox.warning(self, "필수 입력", f"'{spec.label}' 값을 입력해 주세요.")
                return
            payload[spec.key] = value

        if self._platform.key == "youtube":
            payload.setdefault("videos", [])
        if self._platform.key == "twitter":
            payload.setdefault("posts", [])

        self._payload = payload
        self.accept()

    def payload(self) -> dict | None:
        return self._payload
