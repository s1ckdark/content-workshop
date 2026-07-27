"""
Launcher. Performs first-time folder setup, then hands off to the PySide6 UI.
The legacy interactive menu has been replaced by the UI; cron.py is still used
as a subprocess by the scheduler when a recurring job fires.
"""

import sys

from art import print_banner
from config import assert_folder_structure, get_first_time_running
from termcolor import colored
from utils import rem_temp_files


def main() -> int:
    print_banner()

    if get_first_time_running():
        print(
            colored(
                "컨텐츠제작소를 처음 실행하는 것 같습니다. 작업 환경부터 준비하겠습니다.",
                "yellow",
            )
        )

    assert_folder_structure()
    rem_temp_files()

    try:
        from ui.app import run_app
    except ImportError as exc:
        print(
            colored(
                f"PySide6를 불러오지 못했습니다: {exc}\n  pip install -r requirements.txt 로 의존성을 설치해 주세요.",
                "red",
            )
        )
        return 1

    return run_app()


if __name__ == "__main__":
    sys.exit(main())
