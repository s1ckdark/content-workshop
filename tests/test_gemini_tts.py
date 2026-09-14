import wave

import pytest

import classes.Tts as tts_module
from classes.Tts import TTS, unsupported_language_reason
from gemini_client import GeminiError
from gemini_tts import build_tts_payload, synthesize_gemini


def test_payload_without_style_sends_plain_text():
    payload = build_tts_payload("안녕하세요.", "Kore")
    assert payload["contents"][0]["parts"][0]["text"] == "안녕하세요."
    config = payload["generationConfig"]
    assert config["responseModalities"] == ["AUDIO"]
    assert config["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Kore"


def test_payload_with_style_labels_transcript():
    text = build_tts_payload("안녕하세요.", "Kore", style="빠르고 단정적으로")["contents"][0]["parts"][0]["text"]
    assert text.startswith("Synthesize speech")
    assert "Style: 빠르고 단정적으로" in text
    assert text.endswith("#### TRANSCRIPT\n안녕하세요.")


def test_synthesize_writes_mono_24k_wav(fake_post, tmp_path):
    pcm = b"\x00\x01" * 2400
    fake_post.queue.append(fake_post.Response(body=fake_post.audio_body(pcm)))
    out = tmp_path / "out.wav"

    assert synthesize_gemini("hi", str(out), retry_delay=0) == str(out)

    with wave.open(str(out), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == 24000
        assert wav_file.getnframes() == 2400
    assert fake_post.calls[0]["url"].endswith("/models/tts-model:generateContent")


def test_synthesize_retries_server_errors(fake_post, tmp_path):
    fake_post.queue.append(fake_post.Response(status_code=500, text="text tokens"))
    fake_post.queue.append(fake_post.Response(body=fake_post.audio_body(b"\x00\x00")))

    synthesize_gemini("hi", str(tmp_path / "out.wav"), retry_delay=0)

    assert len(fake_post.calls) == 2


def test_synthesize_raises_after_retries(fake_post, tmp_path):
    for _ in range(3):
        fake_post.queue.append(fake_post.Response(body=fake_post.text_body("no audio")))

    with pytest.raises(GeminiError, match="오디오"):
        synthesize_gemini("hi", str(tmp_path / "out.wav"), retry_delay=0)
    assert len(fake_post.calls) == 3


def test_tts_gemini_provider_delegates_with_style(monkeypatch, tmp_path):
    captured = {}

    def fake_synthesize(text, output_file, style=None):
        captured.update(text=text, output_file=output_file, style=style)
        return output_file

    monkeypatch.setattr(tts_module, "synthesize_gemini", fake_synthesize)
    tts = TTS()

    assert tts.provider == "gemini"
    assert tts.synthesize("hi", str(tmp_path / "a.wav"), style="calm") == str(tmp_path / "a.wav")
    assert captured == {"text": "hi", "output_file": str(tmp_path / "a.wav"), "style": "calm"}


def test_tts_rejects_unknown_provider():
    with pytest.raises(ValueError, match="tts_provider"):
        TTS(provider="bogus")


def test_unsupported_language_reason_blocks_kittentts_non_english():
    reason = unsupported_language_reason("kittentts", "korean")
    assert reason is not None
    assert "영어" in reason


def test_unsupported_language_reason_allows_kittentts_english():
    assert unsupported_language_reason("kittentts", "english") is None
    assert unsupported_language_reason("kittentts", "English ") is None
    assert unsupported_language_reason("kittentts", "") is None


def test_unsupported_language_reason_allows_gemini_any_language():
    assert unsupported_language_reason("gemini", "korean") is None
