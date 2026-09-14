import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QComboBox

import templates


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(templates, "get_templates_path", lambda: str(tmp_path / "templates.json"))


TEMPLATE = {
    "id": "t1",
    "name": "money",
    "created_at": "2026-09-14T10:00:00",
    "source_urls": ["https://www.youtube.com/watch?v=AAAAAAAAAAA"],
    "niche": "habits",
    "topic_angle": "angle",
    "hook_pattern": "hook",
    "tone": "tone",
    "language": "korean",
    "sentence_count": 5,
    "visual_style": "style",
    "subtitle_color": "#FFFFFF",
    "example_topics": ["a", "b"],
    "avoid": ["x"],
    "analyses": [{"topic": "x"}],
}


def test_review_dialog_returns_edited_template(qapp, monkeypatch):
    from ui import template_dialog
    from ui.template_dialog import TemplateReviewDialog

    monkeypatch.setattr(template_dialog.QMessageBox, "warning", lambda *a, **k: None)
    dialog = TemplateReviewDialog(TEMPLATE)
    dialog._name.setText("money v2")
    dialog._sentence_count.setValue(8)
    dialog._example_topics.setPlainText("new one\n\n new two ")
    dialog._on_accept()

    result = dialog.result_template()
    assert result["name"] == "money v2"
    assert result["sentence_count"] == 8
    assert result["example_topics"] == ["new one", "new two"]
    assert result["id"] == "t1"
    assert result["analyses"] == TEMPLATE["analyses"]


def test_review_dialog_rejects_bad_color(qapp, monkeypatch):
    from ui import template_dialog
    from ui.template_dialog import TemplateReviewDialog

    warnings = []
    monkeypatch.setattr(template_dialog.QMessageBox, "warning", lambda *a, **k: warnings.append(a))
    dialog = TemplateReviewDialog(TEMPLATE)
    dialog._subtitle_color.setText("yellow")
    dialog._on_accept()

    assert dialog.result_template() is None
    assert warnings


def test_input_dialog_blocks_invalid_urls(qapp, monkeypatch):
    from ui import template_dialog
    from ui.template_dialog import TemplateInputDialog

    warnings = []
    monkeypatch.setattr(template_dialog.QMessageBox, "warning", lambda *a, **k: warnings.append(a[2]))
    dialog = TemplateInputDialog()
    dialog._name.setText("n")
    dialog._urls.setPlainText("https://vimeo.com/1\nhttps://youtu.be/dQw4w9WgXcQ")
    dialog._on_accept()

    assert "vimeo" in warnings[0]
    assert dialog.values() == ("", [])

    dialog._urls.setPlainText("https://youtu.be/dQw4w9WgXcQ")
    dialog._on_accept()
    assert dialog.values() == ("n", ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"])


def test_account_dialog_renders_template_choice(qapp, store):
    templates.add_template({"id": "t1", "name": "money"})
    from ui.account_dialog import AccountDialog
    from ui.platforms import find_platform

    dialog = AccountDialog(find_platform("youtube"))
    combo = dialog._inputs["template_id"]
    assert isinstance(combo, QComboBox)
    assert [combo.itemText(i) for i in range(combo.count())] == ["사용 안 함", "money"]

    dialog._inputs["nickname"].setText("nick")
    dialog._inputs["browser_profile"].setText("/tmp/profile")
    dialog._inputs["niche"].setText("niche")
    dialog._inputs["language"].setText("korean")
    combo.setCurrentIndex(1)
    dialog._on_accept()

    assert dialog.payload()["template_id"] == "t1"


def test_templates_platform_rows_and_remove_warning(qapp, store, monkeypatch):
    templates.add_template({"id": "t1", "name": "money", "source_urls": ["a", "b"]})
    import ui.platforms as platforms

    monkeypatch.setattr(platforms, "get_accounts", lambda provider: [{"template_id": "t1"}])
    platform = platforms.find_platform("templates")

    rows = platform.list_fn()
    assert rows[0]["reference_count"] == 2
    assert "1개" in platform.remove_warning_fn("t1")
    assert platform.custom_add is not None and platform.edit_fn is not None
