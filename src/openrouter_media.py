"""Image generation, narration and timed captions using one OpenRouter key."""

import base64
import binascii
import io
import math
import os
import tempfile
import time
import wave
from pathlib import Path

from config import (
    get_image_aspect_ratio,
    get_image_model,
    get_openrouter_stt_model,
    get_openrouter_tts_model,
    get_openrouter_tts_voice,
)
from openrouter_client import OpenRouterError, post_audio, post_json


def generate_image(prompt: str) -> bytes:
    from PIL import Image, UnidentifiedImageError

    body = post_json("images", {
        "model": get_image_model(),
        "prompt": prompt,
        "aspect_ratio": get_image_aspect_ratio(),
        "resolution": "1K",
        "n": 1,
    })
    for item in body.get("data") or []:
        if not isinstance(item, dict) or not item.get("b64_json"):
            continue
        try:
            raw = base64.b64decode(item["b64_json"], validate=True)
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
                png = io.BytesIO()
                image.convert("RGB").save(png, format="PNG")
                return png.getvalue()
        except (ValueError, binascii.Error, UnidentifiedImageError, OSError):
            raise OpenRouterError("OpenRouter가 올바른 래스터 이미지를 반환하지 않았습니다.") from None
    raise OpenRouterError("OpenRouter 응답에 이미지가 없습니다.")


def build_tts_payload(text: str, voice: str, style: str | None = None) -> dict:
    model = get_openrouter_tts_model()
    payload = {
        "model": model,
        "input": text,
        "voice": voice,
        # Gemini's OpenRouter adapter only supports 24 kHz mono PCM.
        "response_format": "pcm" if model.startswith("google/gemini-") else "mp3",
    }
    if style and style.strip():
        payload["instructions"] = style.strip()
    return payload


def _audio_to_wav(audio: bytes, output_file: str, audio_format: str) -> str:
    import soundfile as sf

    if audio_format == "pcm" and not audio.startswith(b"RIFF"):
        if not audio or len(audio) % 2:
            raise OpenRouterError("OpenRouter PCM 오디오가 올바르지 않습니다.")
        container = io.BytesIO()
        with wave.open(container, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            wav.writeframes(audio)
        audio = container.getvalue()
    try:
        samples, sample_rate = sf.read(io.BytesIO(audio), dtype="int16", always_2d=True)
    except (RuntimeError, ValueError):
        raise OpenRouterError("OpenRouter 오디오를 디코딩할 수 없습니다.") from None
    if not len(samples):
        raise OpenRouterError("OpenRouter 오디오가 비어 있습니다.")
    parent = Path(output_file).resolve().parent
    fd, temporary = tempfile.mkstemp(dir=parent, suffix=".wav")
    os.close(fd)
    try:
        sf.write(temporary, samples, sample_rate, subtype="PCM_16", format="WAV")
        os.replace(temporary, output_file)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return output_file


def synthesize_speech(
    text: str, output_file: str, style: str | None = None,
    retries: int = 2, retry_delay: float = 2.0,
) -> str:
    payload = build_tts_payload(text, get_openrouter_tts_voice(), style)
    for attempt in range(retries + 1):
        try:
            return _audio_to_wav(post_audio(payload), output_file, payload["response_format"])
        except OpenRouterError as exc:
            if not exc.retryable or attempt == retries:
                raise
            time.sleep(retry_delay)
    raise OpenRouterError("음성 합성에 실패했습니다.")


def _timestamp(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3600000)
    minutes, millis = divmod(millis, 60000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def transcript_to_srt(body: dict) -> str:
    segments = body.get("segments")
    if not segments:
        words = body.get("words") or []
        segments = [
            {
                "start": chunk[0].get("start"),
                "end": chunk[-1].get("end"),
                "text": " ".join(str(word.get("word", "")).strip() for word in chunk),
            }
            for index in range(0, len(words), 6)
            if (chunk := words[index:index + 6])
        ]
    if not isinstance(segments, list) or not segments:
        raise OpenRouterError("STT 응답에 자막 타임스탬프가 없습니다. verbose_json 지원 모델을 사용하세요.")
    blocks = []
    previous_end = 0.0
    for segment in segments:
        try:
            start, end = float(segment["start"]), float(segment["end"])
            text = str(segment["text"]).strip()
        except (KeyError, TypeError, ValueError):
            raise OpenRouterError("STT 자막 구간이 올바르지 않습니다.") from None
        if not text:
            continue
        if (
            not math.isfinite(start) or not math.isfinite(end)
            or start < 0 or end <= start or start < previous_end - 0.05
            or round(end * 1000) <= round(start * 1000)
        ):
            raise OpenRouterError("STT 자막 타임스탬프가 올바르지 않습니다.")
        blocks.append(f"{len(blocks) + 1}\n{_timestamp(start)} --> {_timestamp(end)}\n{text}\n")
        previous_end = end
    if not blocks:
        raise OpenRouterError("STT 응답에 자막 텍스트가 없습니다.")
    return "\n".join(blocks)


def transcribe_subtitles(audio_path: str, output_file: str, language: str = "") -> str:
    path = Path(audio_path)
    if path.stat().st_size > 25 * 1024 * 1024:
        raise OpenRouterError("자막용 오디오는 25 MiB 이하로 나누어 주세요.")
    payload = {
        "model": get_openrouter_stt_model(),
        "input_audio": {
            "data": base64.b64encode(path.read_bytes()).decode("ascii"),
            "format": path.suffix.lstrip(".").lower(),
        },
        "response_format": "verbose_json",
        "timestamp_granularities": ["segment", "word"],
    }
    normalized = language.strip().lower()
    code = {"korean": "ko", "한국어": "ko", "english": "en", "japanese": "ja"}.get(normalized, normalized)
    if len(code) == 2 and code.isascii() and code.isalpha():
        payload["language"] = code
    subtitles = transcript_to_srt(post_json("audio/transcriptions", payload))
    Path(output_file).write_text(subtitles, encoding="utf-8")
    return output_file
