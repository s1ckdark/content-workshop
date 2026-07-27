"""
QApplication entry. Called from src/main.py.
"""

import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def run_app() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run_app())
