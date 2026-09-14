import os
from typing import Optional

from config import ROOT_DIR, get_tts_provider, get_tts_voice
from gemini_tts import synthesize_gemini

KITTEN_MODEL = "KittenML/kitten-tts-mini-0.8"
KITTEN_SAMPLE_RATE = 24000
SUPPORTED_PROVIDERS = ("kittentts", "gemini")


class TTS:
    def __init__(self, provider: Optional[str] = None) -> None:
        self._provider = str(provider or get_tts_provider()).strip().lower()
        if self._provider not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"지원하지 않는 tts_provider입니다: '{self._provider}' "
                f"(사용 가능: {', '.join(SUPPORTED_PROVIDERS)})"
            )

        self._voice = get_tts_voice()
        self._model = None
        if self._provider == "kittentts":
            from kittentts import KittenTTS as KittenModel

            self._model = KittenModel(KITTEN_MODEL)

    @property
    def provider(self) -> str:
        return self._provider

    def synthesize(
        self,
        text,
        output_file=os.path.join(ROOT_DIR, ".mp", "audio.wav"),
        style: Optional[str] = None,
    ):
        if self._provider == "gemini":
            return synthesize_gemini(text, output_file, style=style)

        # KittenTTS is English-only and has no style control; style is ignored.
        import soundfile as sf

        audio = self._model.generate(text, voice=self._voice)
        sf.write(output_file, audio, KITTEN_SAMPLE_RATE)
        return output_file
