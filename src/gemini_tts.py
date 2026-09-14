"""
Gemini TTS provider. Gemini returns raw 16-bit mono 24kHz PCM, which is
wrapped as WAV so MoviePy and Whisper keep consuming .wav files.
"""

import time
import wave
from typing import Optional

from config import get_gemini_tts_model, get_gemini_tts_voice
from gemini_client import GeminiError, generate_content, response_inline_data

PCM_SAMPLE_RATE = 24000
PCM_SAMPLE_WIDTH = 2
PCM_CHANNELS = 1


def build_tts_payload(text: str, voice: str, style: Optional[str] = None) -> dict:
    if style and style.strip():
        # An explicit preamble and transcript label keep the model from
        # reading the style notes aloud or rejecting a vague prompt.
        prompt = (
            "Synthesize speech for the transcript below. Read only the transcript aloud.\n"
            f"Director's notes - Style: {style.strip()}\n\n"
            f"#### TRANSCRIPT\n{text}"
        )
    else:
        prompt = text

    return {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }


def pcm_to_wav(pcm: bytes, output_file: str) -> str:
    with wave.open(output_file, "wb") as wav_file:
        wav_file.setnchannels(PCM_CHANNELS)
        wav_file.setsampwidth(PCM_SAMPLE_WIDTH)
        wav_file.setframerate(PCM_SAMPLE_RATE)
        wav_file.writeframes(pcm)
    return output_file


def synthesize_gemini(
    text: str,
    output_file: str,
    style: Optional[str] = None,
    retries: int = 2,
    retry_delay: float = 2.0,
) -> str:
    """
    Synthesizes speech to output_file.

    Gemini TTS occasionally returns text tokens instead of audio (HTTP 500),
    so any failure is retried `retries` times before raising.

    Raises:
        GeminiError: Every attempt failed.
    """
    payload = build_tts_payload(text, get_gemini_tts_voice(), style)
    last_error: GeminiError = GeminiError("Gemini TTS 응답에 오디오가 없습니다.")

    for attempt in range(retries + 1):
        try:
            audio = response_inline_data(generate_content(get_gemini_tts_model(), payload), "audio/")
            if audio:
                return pcm_to_wav(audio, output_file)
            last_error = GeminiError("Gemini TTS 응답에 오디오가 없습니다.")
        except GeminiError as exc:
            last_error = exc
        if attempt < retries:
            time.sleep(retry_delay)

    raise last_error
