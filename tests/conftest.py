"""
Shared pytest setup.

- Puts src/ first on sys.path so bare imports work and config.ROOT_DIR
  resolves to the project root (it is computed from sys.path[0]).
- Injects an in-memory config so tests never read config.json.
- Replaces requests.post for Gemini calls so tests never hit the network.
"""

import base64
import json
import os
import sys
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

import config  # noqa: E402

TEST_CONFIG = {
    "verbose": False,
    "headless": True,
    "threads": 1,
    "font": "bold_font.ttf",
    "imagemagick_path": "/usr/bin/convert",
    "script_sentence_length": 4,
    "nanobanana2_api_base_url": "https://example.test/v1beta",
    "nanobanana2_api_key": "test-key",
    "reference_analysis_model": "analysis-model",
    "tts_provider": "gemini",
    "tts_voice": "Jasper",
    "gemini_tts_model": "tts-model",
    "gemini_tts_voice": "Kore",
}


@pytest.fixture(autouse=True)
def test_config(monkeypatch):
    monkeypatch.setattr(config, "_CONFIG_CACHE", dict(TEST_CONFIG))
    return config._CONFIG_CACHE


class FakeResponse:
    def __init__(self, status_code: int = 200, body: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.text = text or json.dumps(self._body)

    def json(self) -> dict:
        return self._body


def _text_body(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def _audio_body(pcm: bytes) -> dict:
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": "audio/L16;codec=pcm;rate=24000",
                                "data": base64.b64encode(pcm).decode("ascii"),
                            }
                        }
                    ]
                }
            }
        ]
    }


@pytest.fixture
def fake_post(monkeypatch):
    import gemini_client

    calls: list[dict] = []
    queue: list = []

    def _post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if not queue:
            raise AssertionError(f"Unexpected Gemini call to {url}")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(gemini_client.requests, "post", _post)
    return SimpleNamespace(
        calls=calls,
        queue=queue,
        Response=FakeResponse,
        text_body=_text_body,
        audio_body=_audio_body,
    )


@pytest.fixture
def analysis_factory():
    def _make(**overrides) -> dict:
        analysis = {
            "url": "https://www.youtube.com/watch?v=AAAAAAAAAAA",
            "topic": "Why coffee after lunch makes you sleepier",
            "hook_text": "Stop drinking coffee right after lunch.",
            "hook_type": "contrarian",
            "beats": ["hook", "reason", "twist", "tip"],
            "sentence_count": 5,
            "duration_sec": 35,
            "tone": "fast and confident",
            "visual_style": "bold flat illustration, high contrast",
            "subtitle_color": "#FFFFFF",
            "language": "korean",
            "why_it_works": "Contradicts a daily habit in the first second.",
        }
        analysis.update(overrides)
        return analysis

    return _make
