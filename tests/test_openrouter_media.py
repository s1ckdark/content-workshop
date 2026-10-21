import base64
import io
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import config
import openrouter_media as media
from openrouter_client import OpenRouterError
from classes.Tts import TTS, unsupported_language_reason
import classes.Tts as tts_module


def wav_audio(sample_rate=16000):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\x00\x01" * 160)
    return stream.getvalue()


class OpenRouterMediaTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(config, "_CONFIG_CACHE", {
            "llm_provider": "openrouter", "tts_provider": "openrouter",
            "openrouter_tts_model": "google/gemini-3.1-flash-tts-preview",
        }))
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    @patch.object(media, "post_json")
    def test_image_generation_preserves_portrait_ratio_and_normalizes_png(self, post):
        source = io.BytesIO()
        Image.new("RGB", (9, 16), "red").save(source, format="JPEG")
        post.return_value = {"data": [{"b64_json": base64.b64encode(source.getvalue()).decode()}]}
        result = media.generate_image("portrait")
        with Image.open(io.BytesIO(result)) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.size, (9, 16))
        self.assertEqual(post.call_args.args[0], "images")
        self.assertEqual(post.call_args.args[1]["aspect_ratio"], "9:16")
        self.assertEqual(post.call_args.args[1]["n"], 1)

    @patch.object(media, "post_json")
    def test_missing_or_invalid_image_fails(self, post):
        for body in ({}, {"data": [{"b64_json": "invalid!"}]}):
            post.return_value = body
            with self.assertRaises(OpenRouterError):
                media.generate_image("portrait")

    def test_tts_style_is_separate_from_verbatim_transcript(self):
        payload = media.build_tts_payload("안녕하세요.", "Kore", "calm")
        self.assertEqual(payload["input"], "안녕하세요.")
        self.assertEqual(payload["instructions"], "calm")
        self.assertEqual(payload["voice"], "Kore")
        self.assertEqual(payload["response_format"], "pcm")
        self.assertNotIn("instructions", media.build_tts_payload("hi", "Kore"))

    @patch.object(media, "post_audio", return_value=wav_audio())
    def test_tts_writes_valid_wav_preserving_actual_sample_rate(self, post):
        output = self.tmp / "speech.wav"
        media.synthesize_speech("hi", str(output))
        with wave.open(str(output)) as audio:
            self.assertEqual(audio.getframerate(), 16000)
            self.assertEqual(audio.getnframes(), 160)
            self.assertEqual(audio.getsampwidth(), 2)

    @patch.object(media, "post_audio", return_value=b"\x00\x01" * 240)
    def test_gemini_pcm_is_wrapped_as_24k_mono_wav(self, post):
        output = self.tmp / "speech.wav"
        media.synthesize_speech("hi", str(output))
        with wave.open(str(output)) as audio:
            self.assertEqual(audio.getframerate(), 24000)
            self.assertEqual(audio.getnchannels(), 1)
            self.assertEqual(audio.getnframes(), 240)

    @patch.object(media, "post_audio")
    def test_tts_retries_transient_errors(self, post):
        post.side_effect = [OpenRouterError("retry", 503), wav_audio()]
        media.synthesize_speech("hi", str(self.tmp / "speech.wav"), retry_delay=0)
        self.assertEqual(post.call_count, 2)

    @patch.object(media, "post_audio")
    def test_tts_does_not_retry_auth_failure_or_overwrite_existing_file(self, post):
        post.side_effect = OpenRouterError("unauthorized", 401)
        output = self.tmp / "speech.wav"
        output.write_bytes(b"existing")
        with self.assertRaises(OpenRouterError):
            media.synthesize_speech("hi", str(output), retry_delay=0)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(output.read_bytes(), b"existing")

    @patch.object(media, "post_audio", return_value=b"not audio")
    def test_tts_rejects_invalid_audio_after_bounded_retries(self, post):
        output = self.tmp / "speech.wav"
        with self.assertRaises(OpenRouterError):
            media.synthesize_speech("hi", str(output), retry_delay=0)
        self.assertEqual(post.call_count, 3)
        self.assertFalse(output.exists())

    @patch.object(tts_module, "synthesize_speech")
    def test_tts_class_uses_openrouter_without_loading_kitten(self, synthesize):
        synthesize.return_value = "out.wav"
        tts = TTS()
        self.assertEqual(tts.provider, "openrouter")
        self.assertIsNone(tts._model)
        self.assertEqual(tts.synthesize("안녕", "out.wav", style="calm"), "out.wav")
        synthesize.assert_called_once_with("안녕", "out.wav", style="calm")

    def test_tts_provider_and_language_validation(self):
        with self.assertRaises(ValueError):
            TTS(provider="bogus")
        self.assertEqual(TTS(provider="gemini").provider, "openrouter")
        self.assertIsNone(unsupported_language_reason("openrouter", "korean"))
        self.assertIsNotNone(unsupported_language_reason("kittentts", "korean"))
        self.assertIsNone(unsupported_language_reason("kittentts", "English"))

    def test_srt_uses_provider_timestamps(self):
        result = media.transcript_to_srt({"segments": [
            {"start": 0.25, "end": 1.75, "text": "안녕하세요."},
            {"start": 2.0, "end": 3.1, "text": "반갑습니다."},
        ]})
        self.assertIn("00:00:00,250 --> 00:00:01,750", result)
        self.assertIn("2\n00:00:02,000 --> 00:00:03,100", result)

    def test_srt_uses_word_timestamps_if_segments_absent(self):
        result = media.transcript_to_srt({"words": [
            {"start": 0, "end": 1, "word": "hello"},
            {"start": 1, "end": 2, "word": "world"},
        ]})
        self.assertIn("00:00:00,000 --> 00:00:02,000\nhello world", result)

    def test_srt_rejects_missing_or_invalid_timing(self):
        cases = [
            {"text": "plain transcript"},
            {"segments": [{"start": 2, "end": 1, "text": "backwards"}]},
            {"segments": [{"start": float("nan"), "end": 1, "text": "invalid"}]},
            {"segments": [{"start": -1, "end": 1, "text": "negative"}]},
        ]
        for body in cases:
            with self.assertRaises(OpenRouterError):
                media.transcript_to_srt(body)

    @patch.object(media, "post_json")
    def test_transcription_sends_audio_and_requests_timestamps(self, post):
        audio = self.tmp / "input.wav"
        audio.write_bytes(wav_audio())
        output = self.tmp / "out.srt"
        post.return_value = {"segments": [{"start": 0, "end": 1, "text": "안녕"}]}
        media.transcribe_subtitles(str(audio), str(output), "korean")
        path, payload = post.call_args.args
        self.assertEqual(path, "audio/transcriptions")
        self.assertEqual(payload["language"], "ko")
        self.assertEqual(payload["response_format"], "verbose_json")
        self.assertEqual(payload["timestamp_granularities"], ["segment", "word"])
        self.assertEqual(base64.b64decode(payload["input_audio"]["data"]), audio.read_bytes())
        self.assertIn("안녕", output.read_text())

    def test_youtube_saves_openrouter_image_and_thumbnail(self):
        import classes.YouTube as youtube_module

        output = io.BytesIO()
        Image.new("RGB", (9, 16), "blue").save(output, format="PNG")
        (self.tmp / ".mp").mkdir()
        youtube = youtube_module.YouTube.__new__(youtube_module.YouTube)
        youtube.images = []
        youtube.title_image_path = None
        youtube.metadata = {"title": "Test"}
        with (
            patch.object(youtube_module, "ROOT_DIR", str(self.tmp)),
            patch.object(youtube_module, "get_verbose", return_value=False),
            patch.object(youtube_module, "generate_openrouter_image", return_value=output.getvalue()) as generate,
        ):
            path = youtube.generate_image("portrait")
        generate.assert_called_once_with("portrait")
        self.assertEqual(Path(path).read_bytes(), output.getvalue())
        self.assertEqual(Path(youtube.metadata["thumbnail_path"]).read_bytes(), output.getvalue())

    def test_youtube_routes_captions_to_openrouter(self):
        import classes.YouTube as youtube_module

        youtube = youtube_module.YouTube.__new__(youtube_module.YouTube)
        youtube._language = "korean"
        with patch.object(youtube_module, "transcribe_subtitles", return_value="out.srt") as transcribe:
            self.assertEqual(youtube.generate_subtitles("input.wav"), "out.srt")
        self.assertEqual(transcribe.call_args.args[0], "input.wav")
        self.assertEqual(transcribe.call_args.args[2], "korean")


if __name__ == "__main__":
    unittest.main()
