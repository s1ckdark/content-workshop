import os
from typing import Optional

from config import ROOT_DIR, get_tts_provider, get_tts_voice
from openrouter_media import synthesize_speech

KITTEN_MODEL = "KittenML/kitten-tts-mini-0.8"
KITTEN_SAMPLE_RATE = 24000
SUPPORTED_PROVIDERS = ("openrouter", "kittentts")


def unsupported_language_reason(provider: str, language: str) -> Optional[str]:
    normalized = str(language or "").strip().lower()
    if provider == "kittentts" and normalized and normalized not in ("english", "en"):
        return f"KittenTTS는 영어만 지원합니다 (요청 언어: {language}). tts_provider를 openrouter로 변경하세요."
    return None


class TTS:
    def __init__(self, provider: Optional[str] = None) -> None:
        self._provider = str(provider or get_tts_provider()).strip().lower()
        if self._provider == "gemini":
            self._provider = "openrouter"
        if self._provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"지원하지 않는 tts_provider입니다: {self._provider}")
        self._model = None
        if self._provider == "kittentts":
            from kittentts import KittenTTS as KittenModel

            self._voice = get_tts_voice()
            self._model = KittenModel(KITTEN_MODEL)

    @property
    def provider(self) -> str:
        return self._provider

    def synthesize(
        self, text, output_file=os.path.join(ROOT_DIR, ".mp", "audio.wav"),
        style: Optional[str] = None,
    ):
        if self._provider == "openrouter":
            return synthesize_speech(text, output_file, style=style)
        import soundfile as sf

        audio = self._model.generate(text, voice=self._voice)
        sf.write(output_file, audio, KITTEN_SAMPLE_RATE)
        return output_file
