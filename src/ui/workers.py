"""
Background workers for long-running pipelines. Each worker is a QObject that
moveToThread()s onto a QThread; JobDialog drives the lifecycle.

Cancellation is cooperative — the worker checks self._cancelled between
sub-steps. We can't kill MoviePy mid-encode or a Nano Banana 2 HTTP call
that's already in flight, so cancel = "stop after the current step".
"""

import os
from typing import List, Optional

from PySide6.QtCore import QObject, Signal, Slot

from classes.ReferenceAnalyzer import analyze
from classes.Tts import TTS, unsupported_language_reason
from classes.YouTube import YouTube
from config import ROOT_DIR, get_nanobanana2_api_key, get_tts_provider
from templates import TemplateCancelled, load_account_template, run_template_pipeline, synthesize
from utils import fetch_songs


class _Cancelled(Exception):
    """Raised inside the worker when cancellation has been requested."""


class VideoWorker(QObject):
    """Runs the full YouTube video generation pipeline on a worker thread."""

    progress = Signal(str, int)   # (phase label, percent 0-100)
    log = Signal(str)             # free-form log line
    finished = Signal(object)     # {"path": str, "metadata": dict, "account": dict}
    failed = Signal(str)          # error message

    def __init__(self, account: dict) -> None:
        super().__init__()
        self._account = account
        self._cancelled = False
        self._yt: Optional[YouTube] = None

    # ------------------------------------------------------------------ public
    def cancel(self) -> None:
        self._cancelled = True

    @Slot()
    def run(self) -> None:
        try:
            self._run()
        except _Cancelled:
            self.failed.emit("사용자가 취소했습니다.")
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            try:
                if self._yt is not None:
                    self._yt.close()
            except Exception:
                pass

    # ------------------------------------------------------------------ steps
    def _check(self) -> None:
        if self._cancelled:
            raise _Cancelled()

    def _ensure_songs(self) -> None:
        fetch_songs()
        songs_dir = os.path.join(ROOT_DIR, "Songs")
        if not os.path.isdir(songs_dir):
            raise RuntimeError(
                "Songs/ 폴더가 없습니다. config.json의 zip_url을 설정하거나 음원 파일을 넣어 주세요."
            )
        supported = (".mp3", ".wav", ".m4a", ".aac", ".ogg")
        has_audio = any(
            name.lower().endswith(supported)
            and os.path.isfile(os.path.join(songs_dir, name))
            for name in os.listdir(songs_dir)
        )
        if not has_audio:
            raise RuntimeError("Songs/ 폴더에 사용할 수 있는 오디오 파일이 없습니다.")

    def _run(self) -> None:
        account = self._account
        self.progress.emit("준비 중", 0)
        self.log.emit(f"계정: {account.get('nickname', '?')}  /  니치: {account.get('niche', '?')}")

        self.progress.emit("배경음 라이브러리 확인", 2)
        self._ensure_songs()
        self._check()

        template, template_warning = load_account_template(account)
        if template_warning:
            self.log.emit(template_warning)
        if template is not None:
            self.log.emit(f"포맷 템플릿: {template.get('name', '')}")

        self.progress.emit("브라우저 컨텍스트 시작", 4)
        self._yt = YouTube(
            account["id"],
            account.get("nickname", ""),
            account.get("browser_profile") or account.get("firefox_profile", ""),
            account.get("niche", ""),
            account.get("language", ""),
            template=template,
        )
        self._check()

        language_error = unsupported_language_reason(get_tts_provider(), self._yt.language)
        if language_error:
            raise RuntimeError(language_error)

        self.progress.emit("주제 생성", 8)
        self._yt.generate_topic()
        self.log.emit(f"주제: {self._yt.subject}")
        self._check()

        self.progress.emit("스크립트 생성", 16)
        self._yt.generate_script()
        self._check()

        self.progress.emit("메타데이터 생성", 24)
        self._yt.generate_metadata()
        self.log.emit(f"제목: {self._yt.metadata['title']}")
        self._check()

        self.progress.emit("이미지 프롬프트 생성", 32)
        self._yt.generate_prompts()
        self.log.emit(f"이미지 프롬프트 {len(self._yt.image_prompts)}개")
        self._check()

        self._image_loop()

        if not self._yt.images:
            raise RuntimeError("생성된 이미지가 없습니다. Nano Banana 2 설정을 확인하세요.")

        self.progress.emit("음성 합성 (TTS)", 75)
        tts = TTS()
        self.log.emit(f"TTS 제공자: {tts.provider}")
        self._yt.generate_script_to_speech(tts)
        self._check()

        self.progress.emit("자막 + 영상 합성 (MoviePy)", 85)
        self.log.emit("MoviePy 인코딩은 도중에 취소할 수 없습니다.")
        path = self._yt.combine()

        self.progress.emit("완료", 100)
        self._yt.video_path = os.path.abspath(path)
        self.finished.emit(
            {
                "path": self._yt.video_path,
                "metadata": dict(self._yt.metadata),
                "account": self._account,
            }
        )

    # ------------------------------------------------------------ image loop
    def _image_loop(self) -> None:
        """
        Per-image progress with cold-start weighting + one retry on None.
        The first image is weighted 2× because Nano Banana 2 first-call latency
        is consistently higher than steady-state.
        """
        prompts = self._yt.image_prompts
        n = len(prompts)
        if n == 0:
            return

        weights = [2.0] + [1.0] * (n - 1)
        total_w = sum(weights)
        phase_start, phase_end = 32, 70
        cumulative = 0.0

        for i, prompt in enumerate(prompts):
            self._check()
            label = "타이틀/커버 이미지" if i == 0 else f"장면 {i + 1}"
            self.log.emit(f"{label} ({i + 1}/{n}) 생성 중...")

            if self._yt.generate_image(prompt) is None:
                self.log.emit(f"{label} 실패, 1회 재시도")
                if self._yt.generate_image(prompt) is None:
                    self.log.emit(f"{label} 재시도 실패, 스킵")

            cumulative += weights[i]
            pct = int(phase_start + (cumulative / total_w) * (phase_end - phase_start))
            self.progress.emit(f"이미지 생성 ({i + 1}/{n})", pct)


class UploadWorker(QObject):
    """
    Uploads an already-rendered video to YouTube. Spins up a fresh YouTube
    instance (with its own Chromium context) so we never hand a Playwright
    object across threads.
    """

    progress = Signal(str, int)
    log = Signal(str)
    finished = Signal(object)   # uploaded video URL
    failed = Signal(str)

    def __init__(self, account: dict, video_path: str, metadata: dict) -> None:
        super().__init__()
        self._account = account
        self._video_path = video_path
        self._metadata = metadata
        self._cancelled = False
        self._yt: Optional[YouTube] = None

    def cancel(self) -> None:
        self._cancelled = True

    def _check(self) -> None:
        if self._cancelled:
            raise _Cancelled()

    @Slot()
    def run(self) -> None:
        try:
            self._run()
        except _Cancelled:
            self.failed.emit("사용자가 취소했습니다.")
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            try:
                if self._yt is not None:
                    self._yt.close()
            except Exception:
                pass

    def _run(self) -> None:
        account = self._account
        self.progress.emit("브라우저 컨텍스트 시작", 5)
        self.log.emit(f"계정: {account.get('nickname', '?')}")
        self.log.emit(f"영상: {self._video_path}")

        self._yt = YouTube(
            account["id"],
            account.get("nickname", ""),
            account.get("browser_profile") or account.get("firefox_profile", ""),
            account.get("niche", ""),
            account.get("language", ""),
        )
        # Replay the state that generate_video would have left on the instance.
        self._yt.metadata = dict(self._metadata)
        self._yt.video_path = self._video_path
        self._check()

        self.progress.emit("YouTube Studio 업로드", 25)
        self.log.emit("Chromium에서 업로드 진행 중. 도중에 끊을 수 없습니다.")

        ok = self._yt.upload_video()
        if not ok:
            raise RuntimeError("upload_video()가 실패를 보고했습니다. 로그를 확인하세요.")

        url = getattr(self._yt, "uploaded_video_url", "")
        self.progress.emit("완료", 100)
        self.log.emit(f"업로드된 URL: {url}")
        self.finished.emit(url)


class TemplateWorker(QObject):
    """Analyzes reference Shorts and synthesizes a format template."""

    progress = Signal(str, int)
    log = Signal(str)
    finished = Signal(object)   # template dict
    failed = Signal(str)

    def __init__(self, urls: List[str], name: str) -> None:
        super().__init__()
        self._urls = urls
        self._name = name
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @Slot()
    def run(self) -> None:
        if not get_nanobanana2_api_key():
            self.failed.emit(
                "Gemini API 키가 설정되지 않았습니다. config.json의 nanobanana2_api_key를 확인하세요."
            )
            return

        try:
            template, _failures = run_template_pipeline(
                self._urls,
                self._name,
                analyze_fn=self._analyze,
                synthesize_fn=synthesize,
                on_progress=self.progress.emit,
                is_cancelled=lambda: self._cancelled,
                on_failure=lambda line: self.log.emit(f"건너뜀: {line}"),
            )
        except TemplateCancelled:
            self.failed.emit("사용자가 취소했습니다.")
            return
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return

        if self._cancelled:
            self.failed.emit("사용자가 취소했습니다.")
            return

        self.progress.emit("완료", 100)
        self.finished.emit(template)

    def _analyze(self, url: str) -> dict:
        result = analyze(url)
        self.log.emit(
            f"분석 완료: {url} — 주제: {result.get('topic', '')} / "
            f"훅 유형: {result.get('hook_type', '')} / "
            f"문장 수: {result.get('sentence_count', '')} / "
            f"톤: {result.get('tone', '')}"
        )
        return result
