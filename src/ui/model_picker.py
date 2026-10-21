"""
LLM model selection. Mirrors main.ensure_model_selected for the UI.
Selection is in-memory (matches CLI behavior — llm_provider stores it module-wide).
"""

from PySide6.QtWidgets import QInputDialog, QMessageBox, QWidget

from config import get_llm_model
from llm_provider import get_active_model, list_models, select_model


def ensure_model_selected(parent: QWidget | None = None) -> bool:
    """Returns True iff an LLM model is selected after this call."""
    if get_active_model():
        return True

    configured = get_llm_model()
    if configured:
        select_model(configured)
        return True

    try:
        models = list_models()
    except Exception as exc:
        QMessageBox.critical(
            parent,
            "LLM 연결 실패",
            f"모델 목록을 가져오지 못했습니다.\n\n{exc}",
        )
        return False

    if not models:
        QMessageBox.warning(
            parent,
            "사용 가능한 모델 없음",
            "사용할 수 있는 모델이 없습니다. 제공자 설정과 모델 접근 권한을 확인해 주세요.",
        )
        return False

    name, ok = QInputDialog.getItem(
        parent,
        "LLM 모델 선택",
        "사용할 모델:",
        models,
        0,
        False,
    )
    if not ok or not name:
        return False

    select_model(name)
    return True
