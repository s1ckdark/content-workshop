"""
Main window — sidebar (platforms) on the left, item table on the right.
Toolbar above the table for add/delete/refresh.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from cache import update_account
from ui.account_dialog import AccountDialog
from ui.job_dialog import JobDialog
from ui.model_picker import ensure_model_selected
from ui.platforms import PLATFORMS, Platform, template_choices
from ui.workers import UploadWorker, VideoWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("컨텐츠제작소")
        self.resize(1100, 700)

        self._sidebar = self._build_sidebar()
        self._content = self._build_content()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._sidebar)
        splitter.addWidget(self._content)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 880])
        self.setCentralWidget(splitter)

        self._sidebar.setCurrentRow(0)

    def _build_sidebar(self) -> QListWidget:
        sidebar = QListWidget()
        sidebar.setMaximumWidth(280)
        for platform in PLATFORMS:
            item = QListWidgetItem(platform.label)
            item.setData(Qt.ItemDataRole.UserRole, platform.key)
            sidebar.addItem(item)
        sidebar.currentRowChanged.connect(self._on_platform_changed)
        return sidebar

    def _build_content(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._toolbar = QToolBar()
        self._toolbar.setMovable(False)

        self._add_action = QAction("+ 추가", self)
        self._add_action.triggered.connect(self._on_add)
        self._toolbar.addAction(self._add_action)

        self._remove_action = QAction("삭제", self)
        self._remove_action.triggered.connect(self._on_remove)
        self._toolbar.addAction(self._remove_action)

        self._refresh_action = QAction("새로고침", self)
        self._refresh_action.triggered.connect(self._reload_table)
        self._toolbar.addAction(self._refresh_action)

        self._toolbar.addSeparator()

        self._run_action = QAction("▶ 영상 생성", self)
        self._run_action.triggered.connect(self._on_run)
        self._toolbar.addAction(self._run_action)

        self._link_action = QAction("템플릿 연결", self)
        self._link_action.triggered.connect(self._on_link_template)
        self._toolbar.addAction(self._link_action)

        self._toolbar.addSeparator()
        self._count_label = QLabel("")
        self._toolbar.addWidget(self._count_label)

        self._table = QTableWidget()
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._on_table_double_click)

        layout.addWidget(self._toolbar)
        layout.addWidget(self._table)
        return container

    @property
    def _current_platform(self) -> Platform:
        return PLATFORMS[max(self._sidebar.currentRow(), 0)]

    def _on_platform_changed(self, _row: int) -> None:
        self._reload_table()

    def _reload_table(self) -> None:
        platform = self._current_platform
        rows = list(platform.list_fn())

        headers = [col[0] for col in platform.columns]
        self._table.clear()
        self._table.setColumnCount(len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            for c, (_, key) in enumerate(platform.columns):
                value = row.get(key, "")
                item = QTableWidgetItem(str(value) if value is not None else "")
                item.setData(Qt.ItemDataRole.UserRole, row.get("id", ""))
                self._table.setItem(r, c, item)

        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        if self._table.columnCount() > 0:
            self._table.horizontalHeader().setSectionResizeMode(
                self._table.columnCount() - 1, QHeaderView.ResizeMode.ResizeToContents
            )

        self._add_action.setEnabled(platform.add_fn is not None or platform.custom_add is not None)
        self._remove_action.setEnabled(platform.remove_fn is not None)
        self._run_action.setEnabled(platform.key == "youtube")
        self._link_action.setEnabled(platform.key == "youtube")
        self._count_label.setText(f"  {len(rows)}개의 {platform.item_label}")

    def _on_add(self) -> None:
        platform = self._current_platform
        if platform.custom_add is not None:
            if platform.custom_add(self):
                self._reload_table()
            return
        if platform.add_fn is None:
            return

        dialog = AccountDialog(platform, self)
        if dialog.exec() == AccountDialog.DialogCode.Accepted:
            payload = dialog.payload()
            if payload is not None:
                platform.add_fn(payload)
                self._reload_table()

    def _on_remove(self) -> None:
        platform = self._current_platform
        if platform.remove_fn is None:
            return

        row = self._table.currentRow()
        if row < 0:
            return

        item = self._table.item(row, 0)
        item_id = item.data(Qt.ItemDataRole.UserRole) if item else ""
        if not item_id:
            return

        message = f"이 {platform.item_label}을(를) 삭제할까요?"
        if platform.remove_warning_fn is not None:
            extra = platform.remove_warning_fn(item_id)
            if extra:
                message = f"{extra}\n\n{message}"
        confirm = QMessageBox.question(self, "삭제 확인", message)
        if confirm == QMessageBox.StandardButton.Yes:
            platform.remove_fn(item_id)
            self._reload_table()

    # ----------------------------------------------------- video generation
    def _on_table_double_click(self, _index) -> None:
        platform = self._current_platform
        if platform.key == "youtube":
            self._on_run()
            return
        if platform.edit_fn is not None:
            row = self._selected_row()
            if row is not None and platform.edit_fn(self, row):
                self._reload_table()

    def _selected_row(self) -> dict | None:
        platform = self._current_platform
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        item_id = item.data(Qt.ItemDataRole.UserRole) if item else ""
        for entry in platform.list_fn():
            if entry.get("id") == item_id:
                return entry
        return None

    def _on_run(self) -> None:
        platform = self._current_platform
        if platform.key != "youtube":
            return

        account = self._selected_row()
        if account is None:
            QMessageBox.information(self, "선택 필요", "먼저 계정을 선택해 주세요.")
            return

        if not ensure_model_selected(self):
            return

        worker = VideoWorker(account)
        dialog = JobDialog(worker, f"영상 생성 — {account.get('nickname', '')}", self)
        dialog.exec()

        result = dialog.result()
        if not isinstance(result, dict):
            return  # cancelled or failed

        path = result["path"]
        metadata = result["metadata"]
        ans = QMessageBox.question(
            self,
            "업로드",
            f"영상이 저장되었습니다:\n{path}\n\n제목: {metadata.get('title', '')}\n\nYouTube에 업로드할까요?",
        )
        if ans != QMessageBox.StandardButton.Yes:
            self._reload_table()
            return

        upload = UploadWorker(account, path, metadata)
        upload_dlg = JobDialog(upload, f"업로드 — {account.get('nickname', '')}", self)
        upload_dlg.exec()

        url = upload_dlg.result()
        if url:
            QMessageBox.information(self, "업로드 완료", f"업로드된 URL:\n{url}")
        self._reload_table()

    def _on_link_template(self) -> None:
        if self._current_platform.key != "youtube":
            return
        account = self._selected_row()
        if account is None:
            QMessageBox.information(self, "선택 필요", "먼저 계정을 선택해 주세요.")
            return

        choices = template_choices()
        labels = [label for label, _ in choices]
        current = next(
            (i for i, (_, value) in enumerate(choices) if value == account.get("template_id", "")), 0
        )
        label, ok = QInputDialog.getItem(
            self, "템플릿 연결", f"{account.get('nickname', '')} 계정의 포맷 템플릿", labels, current, False
        )
        if not ok:
            return

        template_id = choices[labels.index(label)][1]
        update_account("youtube", account["id"], {"template_id": template_id})
        self._reload_table()
