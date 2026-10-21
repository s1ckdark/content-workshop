# 레퍼런스 기반 포맷 템플릿 Implementation Plan

> 2026-10-21 업데이트: 이 문서는 최초 Gemini 직접 호출 설계/계획의 기록입니다. 현재 구현은 OpenRouter를 사용합니다. API 설정과 모델은 [Configuration.md](../../Configuration.md)를 따릅니다.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 레퍼런스 쇼츠 URL에서 포맷 템플릿을 추출·저장하고, 템플릿이 연결된 YouTube 계정의 영상 생성(주제·대본·이미지·자막·한국어 TTS)에 반영한다.

**Architecture:** Gemini REST 호출은 `src/gemini_client.py` 한 곳으로 모으고, 그 위에 영상 분석(`classes/ReferenceAnalyzer.py`), 템플릿 합성·저장(`templates.py`), Gemini TTS(`gemini_tts.py`)를 얹는다. 프롬프트 조립은 순수 함수 모듈 `prompts.py`로 분리해 `YouTube.py`는 호출만 한다. UI는 기존 `Platform` 선언 구조를 확장해 "포맷 템플릿" 사이드바와 계정-템플릿 연결을 추가한다.

**Tech Stack:** Python 3.12, `requests`, PySide6, Gemini API `generateContent` (영상 이해 · 구조화 출력 · TTS), pytest

**Spec:** `docs/superpowers/specs/2026-09-14-reference-format-templates-design.md`

## Global Constraints

- 실행 루트는 항상 프로젝트 루트. 모든 import는 `src/` 기준 bare module 이름 (`from config import ...`, `from classes.Tts import TTS`).
- 테스트 실행: `venv/bin/python -m pytest` (프로젝트 루트에서).
- 테스트는 네트워크를 절대 호출하지 않는다 — `requests.post`는 `fake_post` 픽스처로 대체.
- 테스트는 실제 `config.json`·`.mp/`를 읽거나 쓰지 않는다 — `tests/conftest.py`의 `config._CONFIG_CACHE` 주입과 `tmp_path` 사용.
- Gemini API 키/base URL은 기존 `get_nanobanana2_api_key()` / `get_nanobanana2_api_base_url()` 재사용. 새 키 추가 금지.
- 신규 설정 기본값: `reference_analysis_model="gemini-3.8-flash"`, `tts_provider="kittentts"`, `gemini_tts_model="gemini-3.1-flash-tts-preview"`, `gemini_tts_voice="Kore"`.
- 구조화 출력 요청 형식: `generationConfig.responseFormat.text = {"mimeType": "application/json", "schema": <JSON Schema>}`.
- Gemini TTS 요청 형식: `generationConfig = {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": <voice>}}}}`, 응답은 `inlineData.data`의 base64 PCM (16-bit, mono, 24kHz).
- `sentence_count`는 3~12로 clamp. 자막 색 기본값 `#FFFF00`. 레퍼런스 URL은 1~10개.
- 템플릿이 없는 계정의 동작은 기존과 같아야 한다 (템플릿 전용 지시가 프롬프트에 섞이지 않음).
- 사용자 노출 메시지는 한국어, 코드·주석·LLM 프롬프트는 영어 (기존 코드 관례).
- 커밋 메시지 끝에 다음 두 줄을 붙인다:
  ```
  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01VjiBfK311eWEGqvmHaBqvY
  ```

## File Structure

| 파일 | 상태 | 책임 |
|---|---|---|
| `requirements.txt` | 수정 | `requests` 명시 |
| `requirements-dev.txt` | 신규 | `pytest` |
| `tests/conftest.py` | 신규 | `src` 경로 주입, 테스트용 config, `fake_post`·`analysis_factory` 픽스처 |
| `src/config.py` | 수정 | 신규 설정 getter 4개 |
| `src/gemini_client.py` | 신규 | Gemini `generateContent` POST, 응답 텍스트/바이너리 추출, JSON 파싱 |
| `src/classes/ReferenceAnalyzer.py` | 신규 | URL 정규화, URL 목록 파싱, 영상 1개 분석 |
| `src/prompts.py` | 신규 | 템플릿 유무에 따른 프롬프트·설정값 해석 (순수 함수) |
| `src/templates.py` | 신규 | 템플릿 저장소, 규칙 기반 병합, Gemini 합성, 분석→합성 파이프라인, 계정 템플릿 로드 |
| `src/gemini_tts.py` | 신규 | Gemini TTS 요청·PCM→WAV·재시도 |
| `src/classes/Tts.py` | 수정 | `tts_provider` 분기, `style` 인자 |
| `src/cache.py` | 수정 | `update_account` |
| `src/classes/YouTube.py` | 수정 | `template` 인자, `prompts.py` 사용, TTS style, 자막 색 |
| `src/ui/workers.py` | 수정 | `TemplateWorker`, `VideoWorker` 템플릿 로드 |
| `src/cron.py` | 수정 | 스케줄 실행에도 템플릿 로드 |
| `src/ui/template_dialog.py` | 신규 | URL 입력 · 검토/수정 다이얼로그, 추가/수정 흐름 |
| `src/ui/platforms.py` | 수정 | "포맷 템플릿" 플랫폼, `choice` 필드, `custom_add`·`edit_fn`·`remove_warning_fn` |
| `src/ui/account_dialog.py` | 수정 | `choice` 필드 렌더링 |
| `src/ui/main_window.py` | 수정 | 커스텀 추가/수정, 삭제 경고, "템플릿 연결" 액션 |
| `config.example.json`, `docs/Configuration.md` | 수정 | 신규 설정 문서화 |

---

### Task 0: 작업 트리 정리와 테스트 기반

**Files:**
- Create: `requirements-dev.txt`
- Create: `tests/conftest.py`
- Create: `tests/test_smoke.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: 없음
- Produces: 픽스처 `fake_post` → `SimpleNamespace(calls: list[dict], queue: list, Response: type, text_body: Callable[[str], dict], audio_body: Callable[[bytes], dict])`, 픽스처 `analysis_factory` → `Callable[..., dict]`, 상수 `TEST_CONFIG: dict`

- [ ] **Step 1: 미커밋 변경 확인 (사람 결정 필요)**

Run: `git status --short --branch`
Expected: `src/classes/YouTube.py`, `src/ui/workers.py`에 기존 미커밋 변경(타이틀 카드·한국어 폰트)이 보인다. 이 두 파일은 Task 7·8에서 수정하므로, **운영자에게 먼저 커밋할지 확인한다.** 운영자가 커밋을 승인하면:

```bash
git add src/classes/YouTube.py src/ui/workers.py
git commit -m "Add title card overlay and Korean font fallback for Shorts"
```

- [ ] **Step 2: 기능 브랜치 생성**

```bash
git switch -c feature/reference-format-templates
```

- [ ] **Step 3: 의존성 파일 작성**

`requirements.txt` 맨 끝에 한 줄 추가:

```
requests
```

`requirements-dev.txt`:

```
-r requirements.txt
pytest
```

설치:

Run: `venv/bin/pip install pytest`
Expected: `Successfully installed pytest-...` 또는 `Requirement already satisfied`

- [ ] **Step 4: conftest 작성**

`tests/conftest.py`:

```python
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
```

`tests/test_smoke.py`:

```python
import os

import config


def test_root_dir_is_project_root():
    assert os.path.isdir(os.path.join(config.ROOT_DIR, "src"))


def test_config_is_injected():
    assert config.get_nanobanana2_api_key() == "test-key"
```

- [ ] **Step 5: 스모크 테스트 실행**

Run: `venv/bin/python -m pytest tests/test_smoke.py -v`
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add requirements.txt requirements-dev.txt tests/conftest.py tests/test_smoke.py
git commit -m "Add pytest scaffolding with offline Gemini fixtures"
```

---

### Task 1: Gemini REST 클라이언트와 설정 getter

**Files:**
- Create: `src/gemini_client.py`
- Modify: `src/config.py` (파일 끝, `get_script_sentence_length` 뒤)
- Test: `tests/test_gemini_client.py`

**Interfaces:**
- Consumes: `fake_post`, `TEST_CONFIG` (Task 0)
- Produces:
  - `class GeminiError(RuntimeError)`
  - `generate_content(model: str, payload: dict, timeout: int = 300) -> dict`
  - `response_text(body: dict) -> str`
  - `response_inline_data(body: dict, mime_prefix: str) -> bytes | None`
  - `parse_json_text(text: str) -> dict`
  - `json_generation_config(schema: dict) -> dict`
  - `config.get_reference_analysis_model() -> str`, `config.get_tts_provider() -> str`, `config.get_gemini_tts_model() -> str`, `config.get_gemini_tts_voice() -> str`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_gemini_client.py`:

```python
import pytest

import config
import gemini_client
from gemini_client import (
    GeminiError,
    generate_content,
    json_generation_config,
    parse_json_text,
    response_inline_data,
    response_text,
)


def test_generate_content_posts_to_model_endpoint(fake_post):
    fake_post.queue.append(fake_post.Response(body=fake_post.text_body("hello")))

    body = generate_content("m1", {"contents": []})

    call = fake_post.calls[0]
    assert call["url"] == "https://example.test/v1beta/models/m1:generateContent"
    assert call["headers"]["x-goog-api-key"] == "test-key"
    assert call["json"] == {"contents": []}
    assert response_text(body) == "hello"


def test_generate_content_raises_on_http_error(fake_post):
    fake_post.queue.append(fake_post.Response(status_code=403, text="forbidden"))

    with pytest.raises(GeminiError, match="403"):
        generate_content("m1", {})


def test_generate_content_requires_api_key(monkeypatch, fake_post):
    monkeypatch.setattr(gemini_client, "get_nanobanana2_api_key", lambda: "")

    with pytest.raises(GeminiError, match="API 키"):
        generate_content("m1", {})
    assert fake_post.calls == []


def test_generate_content_wraps_network_errors(fake_post):
    fake_post.queue.append(gemini_client.requests.ConnectionError("boom"))

    with pytest.raises(GeminiError, match="요청 실패"):
        generate_content("m1", {})


def test_parse_json_text_strips_code_fences():
    assert parse_json_text('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_text_rejects_non_object():
    with pytest.raises(GeminiError):
        parse_json_text("[1, 2]")


def test_parse_json_text_rejects_invalid_json():
    with pytest.raises(GeminiError):
        parse_json_text("not json")


def test_response_inline_data_decodes_matching_mime(fake_post):
    body = fake_post.audio_body(b"\x01\x02")
    assert response_inline_data(body, "audio/") == b"\x01\x02"
    assert response_inline_data(body, "image/") is None


def test_json_generation_config_shape():
    schema = {"type": "object"}
    assert json_generation_config(schema) == {
        "responseFormat": {"text": {"mimeType": "application/json", "schema": schema}}
    }


def test_new_config_getters_read_values():
    assert config.get_reference_analysis_model() == "analysis-model"
    assert config.get_tts_provider() == "gemini"
    assert config.get_gemini_tts_model() == "tts-model"
    assert config.get_gemini_tts_voice() == "Kore"


def test_new_config_getters_defaults(monkeypatch):
    monkeypatch.setattr(config, "_CONFIG_CACHE", {})
    assert config.get_reference_analysis_model() == "gemini-3.8-flash"
    assert config.get_tts_provider() == "kittentts"
    assert config.get_gemini_tts_model() == "gemini-3.1-flash-tts-preview"
    assert config.get_gemini_tts_voice() == "Kore"
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/test_gemini_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gemini_client'`

- [ ] **Step 3: config getter 추가**

`src/config.py` 파일 끝에 추가:

```python

def get_reference_analysis_model() -> str:
    """
    Gets the Gemini model used to analyze reference Shorts and synthesize templates.

    Returns:
        model (str): Model name
    """
    return load_config().get("reference_analysis_model") or "gemini-3.8-flash"

def get_tts_provider() -> str:
    """
    Gets the TTS provider.

    Returns:
        provider (str): "kittentts" or "gemini"
    """
    return str(load_config().get("tts_provider") or "kittentts").strip().lower()

def get_gemini_tts_model() -> str:
    """
    Gets the Gemini TTS model name.

    Returns:
        model (str): Model name
    """
    return load_config().get("gemini_tts_model") or "gemini-3.1-flash-tts-preview"

def get_gemini_tts_voice() -> str:
    """
    Gets the Gemini TTS prebuilt voice name.

    Returns:
        voice (str): Voice name
    """
    return load_config().get("gemini_tts_voice") or "Kore"
```

- [ ] **Step 4: gemini_client 구현**

`src/gemini_client.py`:

```python
"""
Thin REST helper for Gemini generateContent calls shared by reference
analysis, template synthesis and Gemini TTS.
"""

import base64
import json
import re
from typing import Optional

import requests

from config import get_nanobanana2_api_base_url, get_nanobanana2_api_key


class GeminiError(RuntimeError):
    """Raised when a Gemini call fails or returns an unusable payload."""


def generate_content(model: str, payload: dict, timeout: int = 300) -> dict:
    """
    POSTs a generateContent request and returns the parsed JSON body.

    Raises:
        GeminiError: Missing API key, network failure or HTTP error status.
    """
    api_key = get_nanobanana2_api_key()
    if not api_key:
        raise GeminiError(
            "Gemini API 키가 설정되지 않았습니다 (nanobanana2_api_key 또는 GEMINI_API_KEY)."
        )

    endpoint = f"{get_nanobanana2_api_base_url().rstrip('/')}/models/{model}:generateContent"
    try:
        response = requests.post(
            endpoint,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise GeminiError(f"Gemini 요청 실패: {exc}") from exc

    if response.status_code >= 400:
        raise GeminiError(f"Gemini HTTP {response.status_code}: {response.text[:300]}")

    return response.json()


def response_text(body: dict) -> str:
    """Concatenates every text part of every candidate."""
    texts = []
    for candidate in body.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if "text" in part:
                texts.append(part["text"])
    return "".join(texts)


def response_inline_data(body: dict, mime_prefix: str) -> Optional[bytes]:
    """Returns the first inline binary part whose MIME type starts with mime_prefix."""
    for candidate in body.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if not inline:
                continue
            mime_type = inline.get("mimeType") or inline.get("mime_type", "")
            if inline.get("data") and str(mime_type).startswith(mime_prefix):
                return base64.b64decode(inline["data"])
    return None


def parse_json_text(text: str) -> dict:
    """Parses a JSON object, tolerating Markdown code fences around it."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise GeminiError(f"JSON 파싱 실패: {exc}") from exc
    if not isinstance(parsed, dict):
        raise GeminiError("JSON 객체가 아닌 응답입니다.")
    return parsed


def json_generation_config(schema: dict) -> dict:
    """Builds the generationConfig that forces a JSON response matching schema."""
    return {"responseFormat": {"text": {"mimeType": "application/json", "schema": schema}}}
```

- [ ] **Step 5: 통과 확인**

Run: `venv/bin/python -m pytest tests/test_gemini_client.py -v`
Expected: `11 passed`

- [ ] **Step 6: Commit**

```bash
git add src/gemini_client.py src/config.py tests/test_gemini_client.py
git commit -m "Add shared Gemini REST client and template/TTS config getters"
```

---

### Task 2: ReferenceAnalyzer — URL 정규화와 영상 분석

**Files:**
- Create: `src/classes/ReferenceAnalyzer.py`
- Test: `tests/test_reference_analyzer.py`

**Interfaces:**
- Consumes: `generate_content`, `response_text`, `parse_json_text`, `json_generation_config`, `GeminiError` (Task 1), `get_reference_analysis_model` (Task 1)
- Produces:
  - `normalize_youtube_url(url: str) -> str | None` — `https://www.youtube.com/watch?v=<11자 ID>` 형식
  - `parse_url_lines(text: str) -> tuple[list[str], list[str]]` — (정규화된 고유 URL, 잘못된 원문 줄)
  - `analyze(url: str, retries: int = 1) -> dict` — 스펙 5.1 형식, `url` 키 포함
  - `HOOK_TYPES: list[str]`, `ANALYSIS_SCHEMA: dict`, `REQUIRED_KEYS: tuple[str, ...]`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_reference_analyzer.py`:

```python
import json

import pytest

from classes.ReferenceAnalyzer import (
    REQUIRED_KEYS,
    analyze,
    normalize_youtube_url,
    parse_url_lines,
)
from gemini_client import GeminiError

VIDEO = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "raw",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch?v=dQw4w9WgXcQ&t=10s",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://youtube.com/shorts/dQw4w9WgXcQ?feature=share",
        "https://youtu.be/dQw4w9WgXcQ",
        "youtu.be/dQw4w9WgXcQ",
        "  https://www.youtube.com/shorts/dQw4w9WgXcQ  ",
    ],
)
def test_normalize_accepts_youtube_forms(raw):
    assert normalize_youtube_url(raw) == VIDEO


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "https://vimeo.com/123456",
        "https://www.youtube.com/watch?v=short",
        "https://www.youtube.com/shorts/",
        "https://www.youtube.com/channel/UC1234567890",
        "not a url",
    ],
)
def test_normalize_rejects_non_video_urls(raw):
    assert normalize_youtube_url(raw) is None


def test_parse_url_lines_splits_valid_invalid_and_dedupes():
    text = "\n".join(
        [
            "https://youtu.be/dQw4w9WgXcQ",
            "",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
            "https://vimeo.com/1",
        ]
    )
    valid, invalid = parse_url_lines(text)
    assert valid == [VIDEO]
    assert invalid == ["https://vimeo.com/1"]


def _analysis_json(analysis_factory, **overrides):
    data = analysis_factory(**overrides)
    data.pop("url")
    return json.dumps(data)


def test_analyze_sends_video_uri_and_returns_analysis(fake_post, analysis_factory):
    fake_post.queue.append(fake_post.Response(body=fake_post.text_body(_analysis_json(analysis_factory))))

    result = analyze("https://youtube.com/shorts/dQw4w9WgXcQ")

    call = fake_post.calls[0]
    assert call["url"].endswith("/models/analysis-model:generateContent")
    parts = call["json"]["contents"][0]["parts"]
    assert parts[0] == {"file_data": {"file_uri": VIDEO}}
    assert "responseFormat" in call["json"]["generationConfig"]
    assert result["url"] == VIDEO
    assert all(key in result for key in REQUIRED_KEYS)


def test_analyze_retries_once_on_schema_mismatch(fake_post, analysis_factory):
    fake_post.queue.append(fake_post.Response(body=fake_post.text_body('{"topic": "only"}')))
    fake_post.queue.append(fake_post.Response(body=fake_post.text_body(_analysis_json(analysis_factory))))

    result = analyze(VIDEO)

    assert len(fake_post.calls) == 2
    assert result["topic"] == analysis_factory()["topic"]


def test_analyze_raises_after_second_mismatch(fake_post):
    fake_post.queue.append(fake_post.Response(body=fake_post.text_body("oops")))
    fake_post.queue.append(fake_post.Response(body=fake_post.text_body('{"topic": "only"}')))

    with pytest.raises(GeminiError, match="스키마"):
        analyze(VIDEO)
    assert len(fake_post.calls) == 2


def test_analyze_does_not_retry_http_errors(fake_post):
    fake_post.queue.append(fake_post.Response(status_code=400, text="private video"))

    with pytest.raises(GeminiError, match="400"):
        analyze(VIDEO)
    assert len(fake_post.calls) == 1


def test_analyze_rejects_invalid_url_without_calling(fake_post):
    with pytest.raises(GeminiError, match="YouTube URL"):
        analyze("https://vimeo.com/1")
    assert fake_post.calls == []
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/test_reference_analyzer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'classes.ReferenceAnalyzer'`

- [ ] **Step 3: 구현**

`src/classes/ReferenceAnalyzer.py`:

```python
"""
Analyzes a public YouTube Short through Gemini video understanding and
returns a structured description of its format (hook, pacing, tone, visuals).
The video itself is never downloaded.
"""

import re
from typing import List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from config import get_reference_analysis_model
from gemini_client import (
    GeminiError,
    generate_content,
    json_generation_config,
    parse_json_text,
    response_text,
)

_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")

HOOK_TYPES = ["question", "shocking_fact", "contrarian", "list", "story", "other"]

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string", "description": "The concrete topic of this video in one sentence."},
        "hook_text": {"type": "string", "description": "What is said or shown in the first 3 seconds, verbatim."},
        "hook_type": {"type": "string", "enum": HOOK_TYPES},
        "beats": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Ordered narrative beats of the video.",
        },
        "sentence_count": {
            "type": "integer",
            "minimum": 1,
            "maximum": 40,
            "description": "Number of narrated sentences.",
        },
        "duration_sec": {"type": "integer", "minimum": 1, "maximum": 600},
        "tone": {"type": "string", "description": "Narration tone and pacing."},
        "visual_style": {
            "type": "string",
            "description": "Visual style as an English phrase usable as an image-generation prompt suffix.",
        },
        "subtitle_color": {"type": "string", "description": "Dominant caption text color as #RRGGBB."},
        "language": {"type": "string", "description": "Spoken language in lowercase English, e.g. korean."},
        "why_it_works": {"type": "string", "description": "Why this format holds attention."},
    },
    "required": [
        "topic",
        "hook_text",
        "hook_type",
        "beats",
        "sentence_count",
        "duration_sec",
        "tone",
        "visual_style",
        "subtitle_color",
        "language",
        "why_it_works",
    ],
}

REQUIRED_KEYS = tuple(ANALYSIS_SCHEMA["required"])

ANALYSIS_PROMPT = (
    "You are analyzing a YouTube Short so its FORMAT can be reused for different topics.\n"
    "Describe the hook, narrative beats, narration tone and pacing, visual style and caption styling.\n"
    "Count the narrated sentences. Report the spoken language in lowercase English.\n"
    "Answer strictly in the requested JSON schema."
)


def normalize_youtube_url(url: str) -> Optional[str]:
    """
    Normalizes watch, shorts and youtu.be links to a canonical watch URL.

    Returns:
        url (Optional[str]): Canonical URL, or None when url is not a YouTube video link.
    """
    raw = (url or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = "https://" + raw

    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    for prefix in ("www.", "m."):
        if host.startswith(prefix):
            host = host[len(prefix):]

    video_id = ""
    if host == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/")[0]
    elif host == "youtube.com":
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith("/shorts/"):
            video_id = parsed.path.split("/")[2]

    if not _VIDEO_ID.match(video_id):
        return None
    return f"https://www.youtube.com/watch?v={video_id}"


def parse_url_lines(text: str) -> Tuple[List[str], List[str]]:
    """
    Splits multi-line user input into normalized unique URLs and invalid lines.

    Returns:
        (valid, invalid) (Tuple[List[str], List[str]])
    """
    valid: List[str] = []
    invalid: List[str] = []
    for line in (text or "").splitlines():
        raw = line.strip()
        if not raw:
            continue
        normalized = normalize_youtube_url(raw)
        if normalized is None:
            invalid.append(raw)
        elif normalized not in valid:
            valid.append(normalized)
    return valid, invalid


def build_analysis_payload(url: str) -> dict:
    return {
        "contents": [{"parts": [{"file_data": {"file_uri": url}}, {"text": ANALYSIS_PROMPT}]}],
        "generationConfig": json_generation_config(ANALYSIS_SCHEMA),
    }


def validate_analysis(data: dict) -> bool:
    return all(key in data for key in REQUIRED_KEYS) and isinstance(data.get("sentence_count"), int)


def analyze(url: str, retries: int = 1) -> dict:
    """
    Analyzes one public YouTube video.

    HTTP errors (private/deleted video, quota) propagate immediately;
    malformed or schema-mismatched responses are retried `retries` times.

    Raises:
        GeminiError: Invalid URL, HTTP failure or repeated schema mismatch.
    """
    normalized = normalize_youtube_url(url)
    if normalized is None:
        raise GeminiError(f"YouTube URL이 아닙니다: {url}")

    payload = build_analysis_payload(normalized)
    last_error: GeminiError = GeminiError("분석 결과가 스키마와 맞지 않습니다.")
    for _ in range(retries + 1):
        body = generate_content(get_reference_analysis_model(), payload)
        try:
            data = parse_json_text(response_text(body))
        except GeminiError:
            last_error = GeminiError("분석 결과가 스키마와 맞지 않습니다 (JSON 파싱 실패).")
            continue
        if validate_analysis(data):
            data["url"] = normalized
            return data
        last_error = GeminiError("분석 결과가 스키마와 맞지 않습니다.")
    raise last_error
```

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests/test_reference_analyzer.py -v`
Expected: `20 passed`

- [ ] **Step 5: Commit**

```bash
git add src/classes/ReferenceAnalyzer.py tests/test_reference_analyzer.py
git commit -m "Add reference Short analyzer using Gemini video understanding"
```

---

### Task 3: prompts.py — 템플릿 기반 프롬프트 조립

**Files:**
- Create: `src/prompts.py`
- Test: `tests/test_prompts.py`

**Interfaces:**
- Consumes: 없음 (순수 함수)
- Produces:
  - `DEFAULT_SUBTITLE_COLOR = "#FFFF00"`, `HEX_COLOR: re.Pattern`, `MAX_EXISTING_TITLES = 30`
  - `resolve_language(account_language: str, template: dict | None) -> str`
  - `resolve_sentence_count(config_value: int, template: dict | None) -> int`
  - `resolve_subtitle_color(template: dict | None) -> str`
  - `resolve_tts_style(template: dict | None) -> str | None`
  - `build_topic_prompt(niche: str, template: dict | None, existing_titles: list[str]) -> str`
  - `build_script_prompt(subject: str, language: str, sentence_length: int, template: dict | None) -> str`
  - `apply_visual_style(image_prompts: list, template: dict | None) -> list`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_prompts.py`:

```python
from prompts import (
    DEFAULT_SUBTITLE_COLOR,
    MAX_EXISTING_TITLES,
    apply_visual_style,
    build_script_prompt,
    build_topic_prompt,
    resolve_language,
    resolve_sentence_count,
    resolve_subtitle_color,
    resolve_tts_style,
)

TEMPLATE = {
    "niche": "everyday money habits",
    "topic_angle": "hidden losses in daily routines",
    "hook_pattern": "open with a contrarian command",
    "tone": "fast, blunt, informal",
    "language": "korean",
    "sentence_count": 6,
    "visual_style": "bold flat illustration",
    "subtitle_color": "#00FF00",
    "example_topics": ["Why subscriptions drain you"],
    "avoid": ["Stop drinking coffee right after lunch."],
}


def test_topic_prompt_without_template_is_legacy():
    prompt = build_topic_prompt("cooking", None, ["Old title"])
    assert prompt == (
        "Please generate a specific video idea that takes about the following topic: cooking. "
        "Make it exactly one sentence. Only return the topic, nothing else."
    )


def test_topic_prompt_with_template_includes_constraints():
    prompt = build_topic_prompt("fallback niche", TEMPLATE, ["Old title A", "Old title B"])
    assert "everyday money habits" in prompt
    assert "hidden losses in daily routines" in prompt
    assert "Why subscriptions drain you" in prompt
    assert "Stop drinking coffee right after lunch." in prompt
    assert "Old title A" in prompt and "Old title B" in prompt
    assert "fallback niche" not in prompt


def test_topic_prompt_uses_account_niche_when_template_niche_empty():
    prompt = build_topic_prompt("fallback niche", {**TEMPLATE, "niche": ""}, [])
    assert "fallback niche" in prompt


def test_topic_prompt_keeps_only_recent_titles():
    titles = [f"title-{i}" for i in range(MAX_EXISTING_TITLES + 5)]
    prompt = build_topic_prompt("n", TEMPLATE, titles)
    assert "title-4\n" not in prompt
    assert f"title-{MAX_EXISTING_TITLES + 4}" in prompt


def test_script_prompt_without_template_has_no_template_directives():
    prompt = build_script_prompt("Subject X", "english", 4, None)
    assert "Generate a script for a video in 4 sentences" in prompt
    assert "Subject: Subject X" in prompt
    assert "Language: english" in prompt
    assert "HOOK PATTERN" not in prompt
    assert "TONE:" not in prompt


def test_script_prompt_with_template_adds_hook_tone_and_avoid():
    prompt = build_script_prompt("Subject X", "korean", 6, TEMPLATE)
    assert "Generate a script for a video in 6 sentences" in prompt
    assert "HOOK PATTERN: open with a contrarian command" in prompt
    assert "TONE: fast, blunt, informal" in prompt
    assert "Stop drinking coffee right after lunch." in prompt


def test_apply_visual_style_appends_suffix_to_strings_only():
    assert apply_visual_style(["a cat", 3], TEMPLATE) == ["a cat, bold flat illustration", 3]
    assert apply_visual_style(["a cat"], None) == ["a cat"]
    assert apply_visual_style(["a cat"], {**TEMPLATE, "visual_style": " "}) == ["a cat"]


def test_resolvers():
    assert resolve_language("english", TEMPLATE) == "english"
    assert resolve_language("", TEMPLATE) == "korean"
    assert resolve_language("", None) == ""
    assert resolve_sentence_count(4, TEMPLATE) == 6
    assert resolve_sentence_count(4, None) == 4
    assert resolve_sentence_count(4, {"sentence_count": 0}) == 4
    assert resolve_subtitle_color(TEMPLATE) == "#00FF00"
    assert resolve_subtitle_color({"subtitle_color": "yellow"}) == DEFAULT_SUBTITLE_COLOR
    assert resolve_subtitle_color(None) == DEFAULT_SUBTITLE_COLOR
    assert resolve_tts_style(TEMPLATE) == "fast, blunt, informal"
    assert resolve_tts_style({"tone": "  "}) is None
    assert resolve_tts_style(None) is None
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/test_prompts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompts'`

- [ ] **Step 3: 구현**

`src/prompts.py`:

```python
"""
Prompt builders and template resolvers for the YouTube pipeline.
Pure functions so format-template behavior is testable without a browser,
an LLM or MoviePy. With template=None every builder returns the legacy prompt.
"""

import re
from typing import Iterable, List, Optional

DEFAULT_SUBTITLE_COLOR = "#FFFF00"
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
MAX_EXISTING_TITLES = 30


def _bullets(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def resolve_language(account_language: str, template: Optional[dict]) -> str:
    if account_language and account_language.strip():
        return account_language
    return (template or {}).get("language") or account_language


def resolve_sentence_count(config_value: int, template: Optional[dict]) -> int:
    count = (template or {}).get("sentence_count")
    if isinstance(count, int) and count > 0:
        return count
    return config_value


def resolve_subtitle_color(template: Optional[dict]) -> str:
    color = str((template or {}).get("subtitle_color") or "")
    return color if HEX_COLOR.match(color) else DEFAULT_SUBTITLE_COLOR


def resolve_tts_style(template: Optional[dict]) -> Optional[str]:
    tone = str((template or {}).get("tone") or "").strip()
    return tone or None


def build_topic_prompt(niche: str, template: Optional[dict], existing_titles: List[str]) -> str:
    if not template:
        return (
            f"Please generate a specific video idea that takes about the following topic: {niche}. "
            "Make it exactly one sentence. Only return the topic, nothing else."
        )

    sections = [
        "Please generate one specific, original YouTube Shorts video idea.",
        f"Channel niche: {template.get('niche') or niche}",
        f"Topic angle: {template.get('topic_angle', '')}",
    ]
    if template.get("example_topics"):
        sections.append(
            "Examples of topics that fit this channel (do not reuse them verbatim):\n"
            + _bullets(template["example_topics"])
        )
    if template.get("avoid"):
        sections.append(
            "Forbidden topics and lines (never reuse or closely paraphrase):\n"
            + _bullets(template["avoid"])
        )
    titles = [title for title in existing_titles if title][-MAX_EXISTING_TITLES:]
    if titles:
        sections.append(
            "Titles this channel already published (do not repeat these topics):\n" + _bullets(titles)
        )
    sections.append("Make it exactly one sentence. Only return the topic, nothing else.")
    return "\n\n".join(sections)


def build_script_prompt(
    subject: str, language: str, sentence_length: int, template: Optional[dict]
) -> str:
    template_directives = ""
    if template:
        lines = [
            f"THE FIRST SENTENCE IS THE HOOK. FOLLOW THIS HOOK PATTERN: {template.get('hook_pattern', '')}",
            f"TONE: {template.get('tone', '')}",
        ]
        if template.get("avoid"):
            lines.append(
                "NEVER REUSE OR CLOSELY PARAPHRASE THESE LINES OR TOPICS:\n" + _bullets(template["avoid"])
            )
        template_directives = "\n".join(lines) + "\n\n"

    return f"""
        Generate a script for a video in {sentence_length} sentences, depending on the subject of the video.

        The script is to be returned as a string with the specified number of paragraphs.

        Here is an example of a string:
        "This is an example string."

        Do not under any circumstance reference this prompt in your response.

        Get straight to the point, don't start with unnecessary things like, "welcome to this video".

        Obviously, the script should be related to the subject of the video.

        YOU MUST NOT EXCEED THE {sentence_length} SENTENCES LIMIT. MAKE SURE THE {sentence_length} SENTENCES ARE SHORT.
        YOU MUST NOT INCLUDE ANY TYPE OF MARKDOWN OR FORMATTING IN THE SCRIPT, NEVER USE A TITLE.
        YOU MUST WRITE THE SCRIPT IN THE LANGUAGE SPECIFIED IN [LANGUAGE].
        ONLY RETURN THE RAW CONTENT OF THE SCRIPT. DO NOT INCLUDE "VOICEOVER", "NARRATOR" OR SIMILAR INDICATORS OF WHAT SHOULD BE SPOKEN AT THE BEGINNING OF EACH PARAGRAPH OR LINE. YOU MUST NOT MENTION THE PROMPT, OR ANYTHING ABOUT THE SCRIPT ITSELF. ALSO, NEVER TALK ABOUT THE AMOUNT OF PARAGRAPHS OR LINES. JUST WRITE THE SCRIPT

{template_directives}        Subject: {subject}
        Language: {language}
        """


def apply_visual_style(image_prompts: list, template: Optional[dict]) -> list:
    style = str((template or {}).get("visual_style") or "").strip()
    if not style:
        return list(image_prompts)
    return [f"{prompt}, {style}" if isinstance(prompt, str) else prompt for prompt in image_prompts]
```

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests/test_prompts.py -v`
Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add src/prompts.py tests/test_prompts.py
git commit -m "Extract template-aware prompt builders into prompts module"
```

---

### Task 4: templates.py — 저장소와 규칙 기반 병합

**Files:**
- Create: `src/templates.py`
- Test: `tests/test_templates_store.py`

**Interfaces:**
- Consumes: `cache.get_cache_path`, `cache.write_json_atomic`, `prompts.DEFAULT_SUBTITLE_COLOR`, `prompts.HEX_COLOR` (Task 3)
- Produces:
  - `SENTENCE_COUNT_MIN = 3`, `SENTENCE_COUNT_MAX = 12`, `DEFAULT_SENTENCE_COUNT = 4`
  - `get_templates_path() -> str`, `get_templates() -> list[dict]`, `get_template(template_id: str | None) -> dict | None`
  - `add_template(template: dict) -> None`, `update_template(template: dict) -> None` (없으면 `KeyError`), `remove_template(template_id: str) -> None`
  - `aggregate_sentence_counts(counts: list[int]) -> int`
  - `merge_numeric(analyses: list[dict]) -> dict` → `{"sentence_count": int, "subtitle_color": str, "language": str}`
  - `collect_avoid(analyses: list[dict]) -> list[str]`
  - `load_account_template(account: dict) -> tuple[dict | None, str | None]` (템플릿, 경고 메시지)
  - `count_linked_accounts(template_id: str, accounts: list[dict]) -> int`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_templates_store.py`:

```python
import pytest

import templates
from templates import (
    SENTENCE_COUNT_MAX,
    SENTENCE_COUNT_MIN,
    add_template,
    aggregate_sentence_counts,
    collect_avoid,
    count_linked_accounts,
    get_template,
    get_templates,
    load_account_template,
    merge_numeric,
    remove_template,
    update_template,
)


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = tmp_path / "templates.json"
    monkeypatch.setattr(templates, "get_templates_path", lambda: str(path))
    return path


def test_store_roundtrip(store):
    assert get_templates() == []
    add_template({"id": "t1", "name": "A"})
    add_template({"id": "t2", "name": "B"})

    assert [t["id"] for t in get_templates()] == ["t1", "t2"]
    assert get_template("t2")["name"] == "B"
    assert get_template("missing") is None
    assert get_template("") is None
    assert get_template(None) is None


def test_update_and_remove(store):
    add_template({"id": "t1", "name": "A"})
    update_template({"id": "t1", "name": "A2"})
    assert get_template("t1")["name"] == "A2"

    with pytest.raises(KeyError):
        update_template({"id": "nope", "name": "x"})

    remove_template("t1")
    assert get_templates() == []


def test_get_templates_tolerates_corrupt_file(store):
    store.write_text("{not json", encoding="utf-8")
    assert get_templates() == []


def test_aggregate_sentence_counts_median():
    assert aggregate_sentence_counts([5]) == 5
    assert aggregate_sentence_counts([4, 6, 9]) == 6
    assert aggregate_sentence_counts([4, 6]) == 5


def test_merge_numeric_single_analysis(analysis_factory):
    merged = merge_numeric([analysis_factory(sentence_count=7, subtitle_color="#ffffff", language="Korean")])
    assert merged == {"sentence_count": 7, "subtitle_color": "#FFFFFF", "language": "korean"}


def test_merge_numeric_clamps_sentence_count(analysis_factory):
    assert merge_numeric([analysis_factory(sentence_count=1)])["sentence_count"] == SENTENCE_COUNT_MIN
    assert merge_numeric([analysis_factory(sentence_count=30)])["sentence_count"] == SENTENCE_COUNT_MAX


def test_merge_numeric_color_and_language_votes(analysis_factory):
    analyses = [
        analysis_factory(subtitle_color="#FFFF00", language="korean"),
        analysis_factory(subtitle_color="#FFFFFF", language="english"),
        analysis_factory(subtitle_color="yellow", language="korean"),
    ]
    merged = merge_numeric(analyses)
    assert merged["subtitle_color"] == "#FFFF00"
    assert merged["language"] == "korean"


def test_merge_numeric_defaults_when_values_invalid(analysis_factory):
    merged = merge_numeric([analysis_factory(sentence_count="many", subtitle_color="red", language="")])
    assert merged == {"sentence_count": 4, "subtitle_color": "#FFFF00", "language": ""}


def test_collect_avoid_normalizes_and_dedupes(analysis_factory):
    analyses = [
        analysis_factory(topic="Coffee  after lunch", hook_text="Stop now."),
        analysis_factory(topic="Coffee after lunch", hook_text=""),
    ]
    assert collect_avoid(analyses) == ["Coffee after lunch", "Stop now."]


def test_load_account_template(store):
    add_template({"id": "t1", "name": "A"})

    assert load_account_template({"id": "a"}) == (None, None)
    assert load_account_template({"template_id": "t1"}) == ({"id": "t1", "name": "A"}, None)

    template, warning = load_account_template({"template_id": "gone"})
    assert template is None
    assert "gone" in warning


def test_count_linked_accounts():
    accounts = [{"template_id": "t1"}, {"template_id": "t2"}, {"template_id": "t1"}, {}]
    assert count_linked_accounts("t1", accounts) == 2
    assert count_linked_accounts("t9", accounts) == 0
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/test_templates_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'templates'`

- [ ] **Step 3: 구현**

`src/templates.py`:

```python
"""
Format templates: reusable channel formats distilled from reference Shorts.
Stored in .mp/templates.json as {"templates": [...]}.
"""

import json
import os
from collections import Counter
from statistics import median
from typing import List, Optional, Tuple

from cache import get_cache_path, write_json_atomic
from prompts import DEFAULT_SUBTITLE_COLOR, HEX_COLOR

SENTENCE_COUNT_MIN = 3
SENTENCE_COUNT_MAX = 12
DEFAULT_SENTENCE_COUNT = 4


# ------------------------------------------------------------------ storage
def get_templates_path() -> str:
    return os.path.join(get_cache_path(), "templates.json")


def get_templates() -> List[dict]:
    path = get_templates_path()
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            return []
    if not isinstance(data, dict):
        return []
    return data.get("templates", [])


def _save_templates(items: List[dict]) -> None:
    write_json_atomic(get_templates_path(), {"templates": items})


def get_template(template_id: Optional[str]) -> Optional[dict]:
    if not template_id:
        return None
    return next((t for t in get_templates() if t.get("id") == template_id), None)


def add_template(template: dict) -> None:
    items = get_templates()
    items.append(template)
    _save_templates(items)


def update_template(template: dict) -> None:
    items = get_templates()
    for index, existing in enumerate(items):
        if existing.get("id") == template.get("id"):
            items[index] = template
            _save_templates(items)
            return
    raise KeyError(template.get("id"))


def remove_template(template_id: str) -> None:
    _save_templates([t for t in get_templates() if t.get("id") != template_id])


# ---------------------------------------------------------- rule-based merge
def aggregate_sentence_counts(counts: List[int]) -> int:
    """
    Collapses per-reference sentence counts into one target count.

    Decision point: the median keeps the channel at the references' typical
    length. min() would favor the tightest reference; a duration-weighted
    mean would lean toward longer ones.
    """
    return int(round(median(counts)))


def merge_numeric(analyses: List[dict]) -> dict:
    counts = [
        a["sentence_count"]
        for a in analyses
        if isinstance(a.get("sentence_count"), int) and a["sentence_count"] > 0
    ]
    sentence_count = aggregate_sentence_counts(counts) if counts else DEFAULT_SENTENCE_COUNT
    sentence_count = max(SENTENCE_COUNT_MIN, min(SENTENCE_COUNT_MAX, sentence_count))

    colors = [
        str(a.get("subtitle_color", "")).upper()
        for a in analyses
        if HEX_COLOR.match(str(a.get("subtitle_color", "")))
    ]
    subtitle_color = Counter(colors).most_common(1)[0][0] if colors else DEFAULT_SUBTITLE_COLOR

    languages = [str(a.get("language", "")).strip().lower() for a in analyses]
    languages = [language for language in languages if language]
    language = Counter(languages).most_common(1)[0][0] if languages else ""

    return {"sentence_count": sentence_count, "subtitle_color": subtitle_color, "language": language}


def collect_avoid(analyses: List[dict]) -> List[str]:
    avoid: List[str] = []
    for analysis in analyses:
        for key in ("topic", "hook_text"):
            value = " ".join(str(analysis.get(key, "")).split())
            if value and value not in avoid:
                avoid.append(value)
    return avoid


# ---------------------------------------------------------- account linkage
def load_account_template(account: dict) -> Tuple[Optional[dict], Optional[str]]:
    template_id = (account or {}).get("template_id") or ""
    if not template_id:
        return None, None
    template = get_template(template_id)
    if template is None:
        return None, f"연결된 포맷 템플릿({template_id})을 찾을 수 없어 니치 설정으로 생성합니다."
    return template, None


def count_linked_accounts(template_id: str, accounts: List[dict]) -> int:
    return sum(1 for account in accounts if account.get("template_id") == template_id)
```

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests/test_templates_store.py -v`
Expected: `11 passed`

- [ ] **Step 5: Commit**

```bash
git add src/templates.py tests/test_templates_store.py
git commit -m "Add format template store with rule-based merge of reference analyses"
```

---

### Task 5: 템플릿 합성과 분석→합성 파이프라인

**Files:**
- Modify: `src/templates.py` (import 블록과 파일 끝)
- Test: `tests/test_templates_synthesis.py`

**Interfaces:**
- Consumes: `generate_content`, `response_text`, `parse_json_text`, `json_generation_config`, `GeminiError` (Task 1), `get_reference_analysis_model` (Task 1), `merge_numeric`, `collect_avoid` (Task 4)
- Produces:
  - `TEXT_FIELDS: tuple[str, ...]`, `SYNTHESIS_SCHEMA: dict`
  - `build_synthesis_prompt(analyses: list[dict], avoid: list[str]) -> str`
  - `synthesize(analyses: list[dict], name: str, retries: int = 1) -> dict` — 스펙 5.2 형식 템플릿
  - `class TemplateCancelled(Exception)`
  - `run_template_pipeline(urls: list[str], name: str, analyze_fn: Callable[[str], dict], synthesize_fn: Callable[[list[dict], str], dict], on_progress: Callable[[str, int], None], is_cancelled: Callable[[], bool]) -> tuple[dict, list[str]]` — (템플릿, 실패 설명 목록)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_templates_synthesis.py`:

```python
import json

import pytest

from gemini_client import GeminiError
from templates import TemplateCancelled, run_template_pipeline, synthesize

SYNTH = {
    "niche": "생활 속 돈 습관",
    "topic_angle": "일상 속 숨은 손해",
    "hook_pattern": "반대 명령으로 시작",
    "tone": "빠르고 단정적인 반말",
    "visual_style": "bold flat illustration, high contrast",
    "example_topics": ["구독료가 새는 이유", "b", "c", "d", "e"],
}


def test_synthesize_builds_full_template(fake_post, analysis_factory):
    fake_post.queue.append(fake_post.Response(body=fake_post.text_body(json.dumps(SYNTH, ensure_ascii=False))))
    analyses = [
        analysis_factory(url="https://www.youtube.com/watch?v=AAAAAAAAAAA", sentence_count=5),
        analysis_factory(
            url="https://www.youtube.com/watch?v=BBBBBBBBBBB",
            topic="Rent vs buy",
            hook_text="You are losing money.",
            sentence_count=7,
        ),
    ]

    template = synthesize(analyses, "돈 습관")

    assert template["name"] == "돈 습관"
    assert template["id"]
    assert template["created_at"]
    assert template["source_urls"] == [a["url"] for a in analyses]
    assert template["niche"] == "생활 속 돈 습관"
    assert template["example_topics"][0] == "구독료가 새는 이유"
    assert template["sentence_count"] == 6
    assert template["subtitle_color"] == "#FFFFFF"
    assert template["language"] == "korean"
    assert "Rent vs buy" in template["avoid"]
    assert template["analyses"] == analyses

    sent_prompt = fake_post.calls[0]["json"]["contents"][0]["parts"][0]["text"]
    assert "Rent vs buy" in sent_prompt
    assert fake_post.calls[0]["url"].endswith("/models/analysis-model:generateContent")


def test_synthesize_retries_once_then_succeeds(fake_post, analysis_factory):
    fake_post.queue.append(fake_post.Response(body=fake_post.text_body("oops")))
    fake_post.queue.append(fake_post.Response(body=fake_post.text_body(json.dumps(SYNTH))))

    template = synthesize([analysis_factory()], "x")

    assert len(fake_post.calls) == 2
    assert template["tone"] == SYNTH["tone"]


def test_synthesize_retries_http_error_then_raises(fake_post, analysis_factory):
    fake_post.queue.append(fake_post.Response(status_code=500, text="err"))
    fake_post.queue.append(fake_post.Response(body=fake_post.text_body('{"niche": "only"}')))

    with pytest.raises(GeminiError):
        synthesize([analysis_factory()], "x")
    assert len(fake_post.calls) == 2


def test_synthesize_requires_analyses():
    with pytest.raises(ValueError):
        synthesize([], "x")


def _pipeline(urls, analyze_fn, cancelled=lambda: False):
    progress = []
    result = run_template_pipeline(
        urls,
        "name",
        analyze_fn=analyze_fn,
        synthesize_fn=lambda analyses, name: {"name": name, "count": len(analyses)},
        on_progress=lambda label, pct: progress.append((label, pct)),
        is_cancelled=cancelled,
    )
    return result, progress


def test_pipeline_skips_failed_urls():
    def analyze_fn(url):
        if url == "bad":
            raise GeminiError("private video")
        return {"url": url}

    (template, failures), progress = _pipeline(["good1", "bad", "good2"], analyze_fn)

    assert template == {"name": "name", "count": 2}
    assert len(failures) == 1 and "bad" in failures[0] and "private video" in failures[0]
    assert progress[-1] == ("템플릿 합성 중", 85)
    assert [p for _, p in progress] == sorted(p for _, p in progress)


def test_pipeline_raises_when_all_fail():
    def analyze_fn(url):
        raise GeminiError("nope")

    with pytest.raises(RuntimeError, match="모든 레퍼런스"):
        _pipeline(["a", "b"], analyze_fn)


def test_pipeline_honors_cancel():
    with pytest.raises(TemplateCancelled):
        _pipeline(["a"], lambda url: {"url": url}, cancelled=lambda: True)
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/test_templates_synthesis.py -v`
Expected: FAIL — `ImportError: cannot import name 'TemplateCancelled' from 'templates'`

- [ ] **Step 3: import 블록 교체**

`src/templates.py`의 import 블록(모듈 docstring 바로 아래)을 다음으로 교체:

```python
import json
import os
from collections import Counter
from datetime import datetime
from statistics import median
from typing import Callable, List, Optional, Tuple
from uuid import uuid4

from cache import get_cache_path, write_json_atomic
from config import get_reference_analysis_model
from gemini_client import (
    GeminiError,
    generate_content,
    json_generation_config,
    parse_json_text,
    response_text,
)
from prompts import DEFAULT_SUBTITLE_COLOR, HEX_COLOR
```

- [ ] **Step 4: 합성과 파이프라인 구현**

`src/templates.py` 파일 끝에 추가:

```python


# ---------------------------------------------------------------- synthesis
TEXT_FIELDS = ("niche", "topic_angle", "hook_pattern", "tone", "visual_style")

SYNTHESIS_SCHEMA = {
    "type": "object",
    "properties": {
        "niche": {"type": "string", "description": "One-line channel niche summary."},
        "topic_angle": {"type": "string", "description": "How topics are chosen and framed."},
        "hook_pattern": {"type": "string", "description": "Instruction for writing the first sentence."},
        "tone": {"type": "string", "description": "Narration tone and pacing instruction."},
        "visual_style": {
            "type": "string",
            "description": "English image-prompt suffix describing the shared visual style.",
        },
        "example_topics": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 5,
            "maxItems": 5,
            "description": "New topics that fit the format and avoid the forbidden list.",
        },
    },
    "required": ["niche", "topic_angle", "hook_pattern", "tone", "visual_style", "example_topics"],
}


def build_synthesis_prompt(analyses: List[dict], avoid: List[str]) -> str:
    return (
        "You are designing a reusable YouTube Shorts format for a new channel.\n"
        "Below are structured analyses of reference Shorts the operator likes.\n"
        "Extract only what they have in common: format, hook style, tone, visual style and topic angle.\n"
        "Do NOT copy any concrete topic or line. example_topics must be new topics that fit the format "
        "and must not overlap with the forbidden list.\n"
        "Write niche, topic_angle, hook_pattern, tone and example_topics in the references' spoken language. "
        "Write visual_style in English.\n\n"
        f"Forbidden topics and lines:\n{json.dumps(avoid, ensure_ascii=False, indent=2)}\n\n"
        f"Reference analyses:\n{json.dumps(analyses, ensure_ascii=False, indent=2)}"
    )


def _valid_synthesis(data: dict) -> bool:
    return all(isinstance(data.get(key), str) for key in TEXT_FIELDS) and isinstance(
        data.get("example_topics"), list
    )


def synthesize(analyses: List[dict], name: str, retries: int = 1) -> dict:
    """
    Builds a template from per-reference analyses.

    Text fields come from one Gemini call (retried `retries` times on any
    Gemini error or schema mismatch); numeric fields and the avoid list are
    computed locally.
    """
    if not analyses:
        raise ValueError("분석 결과가 없습니다.")

    avoid = collect_avoid(analyses)
    payload = {
        "contents": [{"parts": [{"text": build_synthesis_prompt(analyses, avoid)}]}],
        "generationConfig": json_generation_config(SYNTHESIS_SCHEMA),
    }

    data: Optional[dict] = None
    last_error: GeminiError = GeminiError("합성 결과가 스키마와 맞지 않습니다.")
    for _ in range(retries + 1):
        try:
            candidate = parse_json_text(
                response_text(generate_content(get_reference_analysis_model(), payload))
            )
        except GeminiError as exc:
            last_error = exc
            continue
        if _valid_synthesis(candidate):
            data = candidate
            break
        last_error = GeminiError("합성 결과가 스키마와 맞지 않습니다.")
    if data is None:
        raise last_error

    template = {
        "id": str(uuid4()),
        "name": name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_urls": [analysis.get("url", "") for analysis in analyses],
    }
    template.update({key: data[key].strip() for key in TEXT_FIELDS})
    template["example_topics"] = [
        topic.strip() for topic in data["example_topics"] if isinstance(topic, str) and topic.strip()
    ]
    template.update(merge_numeric(analyses))
    template["avoid"] = avoid
    template["analyses"] = analyses
    return template


# ----------------------------------------------------------------- pipeline
class TemplateCancelled(Exception):
    """Raised when the operator cancels template creation."""


def run_template_pipeline(
    urls: List[str],
    name: str,
    analyze_fn: Callable[[str], dict],
    synthesize_fn: Callable[[List[dict], str], dict],
    on_progress: Callable[[str, int], None],
    is_cancelled: Callable[[], bool],
) -> Tuple[dict, List[str]]:
    """
    Analyzes every URL, skipping failures, then synthesizes one template.

    Returns:
        (template, failures): failures are human-readable "url — reason" lines.

    Raises:
        TemplateCancelled: Cancel requested between steps.
        RuntimeError: Every URL failed to analyze.
    """
    analyses: List[dict] = []
    failures: List[str] = []
    total = len(urls)

    for index, url in enumerate(urls, start=1):
        if is_cancelled():
            raise TemplateCancelled()
        on_progress(f"레퍼런스 분석 중 ({index}/{total})", int(5 + 80 * (index - 1) / total))
        try:
            analyses.append(analyze_fn(url))
        except Exception as exc:
            failures.append(f"{url} — {exc}")

    if not analyses:
        raise RuntimeError("모든 레퍼런스 분석에 실패했습니다:\n" + "\n".join(failures))

    if is_cancelled():
        raise TemplateCancelled()
    on_progress("템플릿 합성 중", 85)
    return synthesize_fn(analyses, name), failures
```

- [ ] **Step 5: 통과 확인 (Task 4 회귀 포함)**

Run: `venv/bin/python -m pytest tests/test_templates_synthesis.py tests/test_templates_store.py -v`
Expected: `18 passed`

- [ ] **Step 6: Commit**

```bash
git add src/templates.py tests/test_templates_synthesis.py
git commit -m "Synthesize format templates from analyses with partial-failure pipeline"
```

---

### Task 6: Gemini TTS 제공자

**Files:**
- Create: `src/gemini_tts.py`
- Modify: `src/classes/Tts.py` (전체 교체)
- Test: `tests/test_gemini_tts.py`

**Interfaces:**
- Consumes: `generate_content`, `response_inline_data`, `GeminiError` (Task 1), `get_gemini_tts_model`, `get_gemini_tts_voice`, `get_tts_provider` (Task 1)
- Produces:
  - `gemini_tts.build_tts_payload(text: str, voice: str, style: str | None = None) -> dict`
  - `gemini_tts.pcm_to_wav(pcm: bytes, output_file: str) -> str`
  - `gemini_tts.synthesize_gemini(text: str, output_file: str, style: str | None = None, retries: int = 2, retry_delay: float = 2.0) -> str`
  - `classes.Tts.TTS(provider: str | None = None)` with `.provider: str` and `.synthesize(text, output_file=..., style: str | None = None) -> str`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_gemini_tts.py`:

```python
import wave

import pytest

import classes.Tts as tts_module
from classes.Tts import TTS
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
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/test_gemini_tts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gemini_tts'`

- [ ] **Step 3: gemini_tts 구현**

`src/gemini_tts.py`:

```python
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
```

- [ ] **Step 4: Tts.py 교체**

`src/classes/Tts.py` 전체를 다음으로 교체 (KittenTTS·soundfile은 kittentts 제공자일 때만 import):

```python
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
```

- [ ] **Step 5: 통과 확인**

Run: `venv/bin/python -m pytest tests/test_gemini_tts.py -v`
Expected: `7 passed`

- [ ] **Step 6: 실제 API 스모크 (선택, 운영자 키 필요)**

`config.json`에 Gemini 키가 있을 때만 수행. 요청 형식이 실제 API와 맞는지 확인하는 유일한 단계다.

Run:
```bash
venv/bin/python -c "import sys; sys.path.insert(0, 'src'); from gemini_tts import synthesize_gemini; print(synthesize_gemini('안녕하세요. 테스트입니다.', '/tmp/gemini_tts_smoke.wav', style='밝고 빠르게'))" && afplay /tmp/gemini_tts_smoke.wav
```
Expected: 경로가 출력되고 한국어 음성이 재생된다. `HTTP 400`이 나오면 에러 본문을 운영자에게 보고하고 `build_tts_payload` 필드명을 공식 문서와 대조한다.

- [ ] **Step 7: Commit**

```bash
git add src/gemini_tts.py src/classes/Tts.py tests/test_gemini_tts.py
git commit -m "Add Gemini TTS provider with style direction and retry"
```

---

### Task 7: YouTube 파이프라인에 템플릿 반영

**Files:**
- Modify: `src/classes/YouTube.py` — import 블록(1-21행 부근), `__init__`(149-179행 부근), `generate_topic`(213-229), `generate_script`(231-277), `generate_prompts`(379-382), `generate_script_to_speech`(542), `combine` 내부 `generator`(699)
- Test: `tests/test_youtube_template.py`

**Interfaces:**
- Consumes: `prompts.*` (Task 3), `TTS.synthesize(..., style=)` (Task 6)
- Produces: `YouTube(account_uuid, account_nickname, fp_profile_path, niche, language, template: dict | None = None)`, 속성 `template: dict | None`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_youtube_template.py`:

```python
from classes.YouTube import YouTube

TEMPLATE = {
    "id": "t1",
    "name": "money",
    "niche": "everyday money habits",
    "topic_angle": "hidden losses",
    "hook_pattern": "contrarian command",
    "tone": "fast and blunt",
    "language": "korean",
    "sentence_count": 6,
    "visual_style": "bold flat illustration",
    "subtitle_color": "#00FF00",
    "example_topics": ["subscriptions"],
    "avoid": ["Stop drinking coffee right after lunch."],
}


def _bare_youtube(template, language=""):
    """Builds a YouTube instance without launching Chromium."""
    yt = YouTube.__new__(YouTube)
    yt._account_uuid = "acc"
    yt._niche = "account niche"
    yt._template = template
    yt._language = language or (template or {}).get("language", "")
    yt.images = []
    return yt


def test_generate_topic_uses_template_and_existing_titles(monkeypatch):
    yt = _bare_youtube(TEMPLATE)
    prompts = []
    monkeypatch.setattr(yt, "generate_response", lambda prompt, model_name=None: prompts.append(prompt) or "New topic")
    monkeypatch.setattr(yt, "get_videos", lambda: [{"title": "Old upload"}])

    assert yt.generate_topic() == "New topic"
    assert "Old upload" in prompts[0]
    assert "Stop drinking coffee right after lunch." in prompts[0]


def test_generate_topic_without_template_keeps_legacy_prompt(monkeypatch):
    yt = _bare_youtube(None, language="english")
    prompts = []
    monkeypatch.setattr(yt, "generate_response", lambda prompt, model_name=None: prompts.append(prompt) or "Topic")
    monkeypatch.setattr(yt, "get_videos", lambda: (_ for _ in ()).throw(AssertionError("must not read videos")))

    yt.generate_topic()

    assert prompts[0].startswith("Please generate a specific video idea that takes about the following topic: account niche.")


def test_generate_script_uses_template_sentence_count(monkeypatch):
    yt = _bare_youtube(TEMPLATE)
    yt.subject = "Subject"
    prompts = []
    monkeypatch.setattr(yt, "generate_response", lambda prompt, model_name=None: prompts.append(prompt) or "한 문장. 두 문장.")

    yt.generate_script()

    assert "in 6 sentences" in prompts[0]
    assert "HOOK PATTERN: contrarian command" in prompts[0]
    assert "Language: korean" in prompts[0]


def test_generate_script_to_speech_passes_template_tone(tmp_path):
    yt = _bare_youtube(TEMPLATE)
    yt.script = "안녕하세요. 반갑습니다!"
    captured = {}

    class FakeTTS:
        def synthesize(self, text, output_file, style=None):
            captured.update(text=text, style=style)
            return output_file

    yt.generate_script_to_speech(FakeTTS())

    assert captured["style"] == "fast and blunt"
    assert captured["text"] == "안녕하세요. 반갑습니다!"


def test_generate_script_to_speech_without_template_passes_no_style():
    yt = _bare_youtube(None, language="english")
    yt.script = "Hello."
    captured = {}

    class FakeTTS:
        def synthesize(self, text, output_file, style=None):
            captured["style"] = style
            return output_file

    yt.generate_script_to_speech(FakeTTS())

    assert captured["style"] is None
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/test_youtube_template.py -v`
Expected: FAIL — 템플릿 테스트에서 `AttributeError`(`_template` 미사용으로 legacy 프롬프트 생성) 또는 `AssertionError` (`in 6 sentences` 없음). import 자체가 실패하면(moviepy/playwright 누락) 에러 전문을 보고하고 중단한다.

- [ ] **Step 3: import 추가**

`src/classes/YouTube.py`의 `from typing import List, Optional` 줄 바로 아래에 추가:

```python
from prompts import (
    apply_visual_style,
    build_script_prompt,
    build_topic_prompt,
    resolve_language,
    resolve_sentence_count,
    resolve_subtitle_color,
    resolve_tts_style,
)
```

- [ ] **Step 4: 생성자 수정**

`__init__` 시그니처·docstring·본문 앞부분을 다음으로 교체 (`self.images = []` 이후 줄은 유지):

```python
    def __init__(
        self,
        account_uuid: str,
        account_nickname: str,
        fp_profile_path: str,
        niche: str,
        language: str,
        template: Optional[dict] = None,
    ) -> None:
        """
        Constructor for YouTube Class.

        Args:
            account_uuid (str): The unique identifier for the YouTube account.
            account_nickname (str): The nickname for the YouTube account.
            fp_profile_path (str): Path to the Chrome user data dir logged into the specified YouTube account.
            niche (str): The niche of the provided YouTube Channel.
            language (str): The language of the Automation.
            template (Optional[dict]): Format template linked to the account, if any.

        Returns:
            None
        """
        self._account_uuid: str = account_uuid
        self._account_nickname: str = account_nickname
        self._fp_profile_path: str = fp_profile_path
        self._niche: str = niche
        self._template: Optional[dict] = template
        self._language: str = resolve_language(language, template)
```

`language` property 아래에 추가:

```python

    @property
    def template(self) -> Optional[dict]:
        """
        Getter Method for the linked format template.

        Returns:
            template (Optional[dict]): The template, or None
        """
        return self._template
```

- [ ] **Step 5: generate_topic 수정**

`generate_topic`의 `completion = self.generate_response(...)` 호출을 다음으로 교체:

```python
        existing_titles = (
            [video.get("title", "") for video in self.get_videos()] if self._template else []
        )
        completion = self.generate_response(
            build_topic_prompt(self.niche, self._template, existing_titles)
        )
```

- [ ] **Step 6: generate_script 수정**

`generate_script`의 `sentence_length = get_script_sentence_length()`부터 `completion = self.generate_response(prompt)` 직전까지(여러 줄 f-string 포함)를 다음으로 교체:

```python
        sentence_length = resolve_sentence_count(get_script_sentence_length(), self._template)
        prompt = build_script_prompt(self.subject, self.language, sentence_length, self._template)
```

- [ ] **Step 7: generate_prompts 수정**

`generate_prompts`에서 `self.image_prompts = image_prompts` 바로 위에 추가:

```python
        image_prompts = apply_visual_style(image_prompts, self._template)
```

- [ ] **Step 8: TTS style·자막 색 반영**

`generate_script_to_speech`의 `tts_instance.synthesize(self.script, path)`를 교체:

```python
        tts_instance.synthesize(self.script, path, style=resolve_tts_style(self._template))
```

`combine`의 `generator` 안 `"color": "#FFFF00",`을 교체:

```python
                "color": resolve_subtitle_color(self._template),
```

- [ ] **Step 9: 통과 확인 (전체 회귀 포함)**

Run: `venv/bin/python -m pytest -v`
Expected: 모든 테스트 통과 (Task 0~7 합계 `71 passed`)

- [ ] **Step 10: Commit**

```bash
git add src/classes/YouTube.py tests/test_youtube_template.py
git commit -m "Apply format templates to topic, script, images, TTS and captions"
```

---

### Task 8: 계정 연결 저장, 작업자·스케줄러 템플릿 로드

**Files:**
- Modify: `src/cache.py` (`remove_account` 뒤)
- Modify: `src/ui/workers.py` (import 블록, `VideoWorker._run`, 파일 끝에 `TemplateWorker`)
- Modify: `src/cron.py` (import 블록, `purpose == "youtube"` 분기)
- Test: `tests/test_account_template_link.py`

**Interfaces:**
- Consumes: `load_account_template`, `run_template_pipeline`, `synthesize`, `TemplateCancelled` (Task 4·5), `analyze` (Task 2), `YouTube(..., template=)` (Task 7)
- Produces:
  - `cache.update_account(provider: str, account_id: str, fields: dict) -> bool`
  - `ui.workers.TemplateWorker(urls: list[str], name: str)` — Signals `progress(str, int)`, `log(str)`, `finished(object)`(템플릿 dict), `failed(str)`; `cancel()`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_account_template_link.py`:

```python
import json

import cache
from cache import add_account, get_accounts, update_account


def test_update_account_merges_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "get_cache_path", lambda: str(tmp_path))
    add_account("youtube", {"id": "a1", "nickname": "n", "videos": []})
    add_account("youtube", {"id": "a2", "nickname": "m", "videos": []})

    assert update_account("youtube", "a2", {"template_id": "t1"}) is True
    assert update_account("youtube", "missing", {"template_id": "t1"}) is False

    accounts = {a["id"]: a for a in get_accounts("youtube")}
    assert accounts["a2"]["template_id"] == "t1"
    assert accounts["a2"]["nickname"] == "m"
    assert "template_id" not in accounts["a1"]
    assert json.loads((tmp_path / "youtube.json").read_text())["accounts"][1]["template_id"] == "t1"
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/test_account_template_link.py -v`
Expected: FAIL — `ImportError: cannot import name 'update_account' from 'cache'`

- [ ] **Step 3: update_account 구현**

`src/cache.py`의 `remove_account` 함수 뒤에 추가:

```python

def update_account(provider: str, account_id: str, fields: dict) -> bool:
    """
    Merges fields into an existing account.

    Args:
        provider (str): The provider ("twitter" or "youtube")
        account_id (str): The ID of the account to update
        fields (dict): Keys to set on the account

    Returns:
        updated (bool): False when no account matches account_id
    """
    accounts = get_accounts(provider)

    for account in accounts:
        if account.get("id") == account_id:
            account.update(fields)
            write_json_atomic(get_provider_cache_path(provider), {"accounts": accounts})
            return True

    return False
```

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests/test_account_template_link.py -v`
Expected: `1 passed`

- [ ] **Step 5: workers.py — import 수정**

`src/ui/workers.py`의 import 블록을 다음으로 교체:

```python
import os
from typing import List, Optional

from PySide6.QtCore import QObject, Signal, Slot

from classes.ReferenceAnalyzer import analyze
from classes.Tts import TTS
from classes.YouTube import YouTube
from config import ROOT_DIR, get_nanobanana2_api_key
from templates import TemplateCancelled, load_account_template, run_template_pipeline, synthesize
from utils import fetch_songs
```

- [ ] **Step 6: VideoWorker._run 수정**

`self.progress.emit("브라우저 컨텍스트 시작", 4)`부터 `self._check()`(YouTube 생성 직후)까지를 다음으로 교체:

```python
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
```

`self._yt.generate_script_to_speech(TTS())` 줄을 교체:

```python
        tts = TTS()
        self.log.emit(f"TTS 제공자: {tts.provider}")
        self._yt.generate_script_to_speech(tts)
```

- [ ] **Step 7: TemplateWorker 추가**

`src/ui/workers.py` 파일 끝에 추가:

```python


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
            template, failures = run_template_pipeline(
                self._urls,
                self._name,
                analyze_fn=self._analyze,
                synthesize_fn=synthesize,
                on_progress=self.progress.emit,
                is_cancelled=lambda: self._cancelled,
            )
        except TemplateCancelled:
            self.failed.emit("사용자가 취소했습니다.")
            return
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return

        for failure in failures:
            self.log.emit(f"건너뜀: {failure}")
        self.progress.emit("완료", 100)
        self.finished.emit(template)

    def _analyze(self, url: str) -> dict:
        result = analyze(url)
        self.log.emit(f"분석 완료: {url} — {result.get('topic', '')}")
        return result
```

- [ ] **Step 8: cron.py 수정**

`src/cron.py` 상단 import 목록에 추가:

```python
from templates import load_account_template
```

`youtube = YouTube(` 호출 블록을 다음으로 교체:

```python
                template, template_warning = load_account_template(acc)
                if template_warning:
                    warning(template_warning)
                youtube = YouTube(
                    acc["id"],
                    acc["nickname"],
                    get_account_browser_profile(acc),
                    acc["niche"],
                    acc["language"],
                    template=template,
                )
```

`warning`은 cron.py 상단의 기존 `from status import *`로 이미 사용 가능하다.

- [ ] **Step 9: import·전체 테스트 확인**

Run: `venv/bin/python -c "import sys; sys.path.insert(0, 'src'); import ui.workers, cron; print('ok')" && venv/bin/python -m pytest -q`
Expected: `ok` 출력 후 `72 passed`

- [ ] **Step 10: Commit**

```bash
git add src/cache.py src/ui/workers.py src/cron.py tests/test_account_template_link.py
git commit -m "Load linked format templates in video worker and scheduler"
```

---

### Task 9: 템플릿 관리 UI

**Files:**
- Create: `src/ui/template_dialog.py`
- Modify: `src/ui/platforms.py` (전체 교체)
- Modify: `src/ui/account_dialog.py` (전체 교체)
- Modify: `src/ui/main_window.py` (import, `_build_content`, `_reload_table`, `_on_add`, `_on_remove`, `_on_table_double_click`, `_selected_account`, `_on_run`, 신규 `_on_link_template`)
- Test: `tests/test_template_ui.py`

**Interfaces:**
- Consumes: `parse_url_lines` (Task 2), `add_template`, `update_template`, `get_template`, `get_templates`, `remove_template`, `count_linked_accounts`, `SENTENCE_COUNT_MIN/MAX` (Task 4), `HEX_COLOR` (Task 3), `update_account` (Task 8), `TemplateWorker` (Task 8)
- Produces:
  - `ui.template_dialog.MAX_REFERENCE_URLS = 10`
  - `TemplateInputDialog(parent)` → `.values() -> tuple[str, list[str]]`
  - `TemplateReviewDialog(template: dict, parent)` → `.result_template() -> dict | None`
  - `add_template_flow(parent) -> bool`, `edit_template_flow(parent, row: dict) -> bool`
  - `FieldSpec.choices_fn: Callable[[], list[tuple[str, str]]] | None`, `FieldSpec.kind` 값 `"choice"`
  - `Platform.custom_add`, `Platform.edit_fn`, `Platform.remove_warning_fn`
  - `ui.platforms.template_choices() -> list[tuple[str, str]]`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_template_ui.py`:

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QComboBox

import templates


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(templates, "get_templates_path", lambda: str(tmp_path / "templates.json"))


TEMPLATE = {
    "id": "t1",
    "name": "money",
    "created_at": "2026-09-14T10:00:00",
    "source_urls": ["https://www.youtube.com/watch?v=AAAAAAAAAAA"],
    "niche": "habits",
    "topic_angle": "angle",
    "hook_pattern": "hook",
    "tone": "tone",
    "language": "korean",
    "sentence_count": 5,
    "visual_style": "style",
    "subtitle_color": "#FFFFFF",
    "example_topics": ["a", "b"],
    "avoid": ["x"],
    "analyses": [{"topic": "x"}],
}


def test_review_dialog_returns_edited_template(qapp, monkeypatch):
    from ui import template_dialog
    from ui.template_dialog import TemplateReviewDialog

    monkeypatch.setattr(template_dialog.QMessageBox, "warning", lambda *a, **k: None)
    dialog = TemplateReviewDialog(TEMPLATE)
    dialog._name.setText("money v2")
    dialog._sentence_count.setValue(8)
    dialog._example_topics.setPlainText("new one\n\n new two ")
    dialog._on_accept()

    result = dialog.result_template()
    assert result["name"] == "money v2"
    assert result["sentence_count"] == 8
    assert result["example_topics"] == ["new one", "new two"]
    assert result["id"] == "t1"
    assert result["analyses"] == TEMPLATE["analyses"]


def test_review_dialog_rejects_bad_color(qapp, monkeypatch):
    from ui import template_dialog
    from ui.template_dialog import TemplateReviewDialog

    warnings = []
    monkeypatch.setattr(template_dialog.QMessageBox, "warning", lambda *a, **k: warnings.append(a))
    dialog = TemplateReviewDialog(TEMPLATE)
    dialog._subtitle_color.setText("yellow")
    dialog._on_accept()

    assert dialog.result_template() is None
    assert warnings


def test_input_dialog_blocks_invalid_urls(qapp, monkeypatch):
    from ui import template_dialog
    from ui.template_dialog import TemplateInputDialog

    warnings = []
    monkeypatch.setattr(template_dialog.QMessageBox, "warning", lambda *a, **k: warnings.append(a[2]))
    dialog = TemplateInputDialog()
    dialog._name.setText("n")
    dialog._urls.setPlainText("https://vimeo.com/1\nhttps://youtu.be/dQw4w9WgXcQ")
    dialog._on_accept()

    assert "vimeo" in warnings[0]
    assert dialog.values() == ("", [])

    dialog._urls.setPlainText("https://youtu.be/dQw4w9WgXcQ")
    dialog._on_accept()
    assert dialog.values() == ("n", ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"])


def test_account_dialog_renders_template_choice(qapp, store):
    templates.add_template({"id": "t1", "name": "money"})
    from ui.account_dialog import AccountDialog
    from ui.platforms import find_platform

    dialog = AccountDialog(find_platform("youtube"))
    combo = dialog._inputs["template_id"]
    assert isinstance(combo, QComboBox)
    assert [combo.itemText(i) for i in range(combo.count())] == ["사용 안 함", "money"]

    dialog._inputs["nickname"].setText("nick")
    dialog._inputs["browser_profile"].setText("/tmp/profile")
    dialog._inputs["niche"].setText("niche")
    dialog._inputs["language"].setText("korean")
    combo.setCurrentIndex(1)
    dialog._on_accept()

    assert dialog.payload()["template_id"] == "t1"


def test_templates_platform_rows_and_remove_warning(qapp, store, monkeypatch):
    templates.add_template({"id": "t1", "name": "money", "source_urls": ["a", "b"]})
    import ui.platforms as platforms

    monkeypatch.setattr(platforms, "get_accounts", lambda provider: [{"template_id": "t1"}])
    platform = platforms.find_platform("templates")

    rows = platform.list_fn()
    assert rows[0]["reference_count"] == 2
    assert "1개" in platform.remove_warning_fn("t1")
    assert platform.custom_add is not None and platform.edit_fn is not None
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/test_template_ui.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ui.template_dialog'`

- [ ] **Step 3: template_dialog 구현**

`src/ui/template_dialog.py`:

```python
"""
Format-template dialogs: reference URL input → analysis job → review/edit → save.
"""

from typing import List, Optional, Tuple

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from classes.ReferenceAnalyzer import parse_url_lines
from prompts import HEX_COLOR
from templates import (
    SENTENCE_COUNT_MAX,
    SENTENCE_COUNT_MIN,
    add_template,
    get_template,
    update_template,
)
from ui.job_dialog import JobDialog
from ui.workers import TemplateWorker

MAX_REFERENCE_URLS = 10


def _lines(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


class TemplateInputDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("포맷 템플릿 — 레퍼런스 입력")
        self.setMinimumWidth(560)

        self._name = QLineEdit()
        self._name.setPlaceholderText("예: 생활 속 돈 습관")
        self._urls = QPlainTextEdit()
        self._urls.setPlaceholderText(
            "좋다고 생각한 쇼츠 URL을 한 줄에 하나씩 (1~10개)\nhttps://www.youtube.com/shorts/..."
        )

        form = QFormLayout()
        form.addRow("템플릿 이름", self._name)
        form.addRow("레퍼런스 URL", self._urls)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("공개 영상만 분석할 수 있습니다. 영상은 다운로드하지 않습니다."))
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._values: Tuple[str, List[str]] = ("", [])

    def _on_accept(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "필수 입력", "템플릿 이름을 입력해 주세요.")
            return

        valid, invalid = parse_url_lines(self._urls.toPlainText())
        if invalid:
            QMessageBox.warning(
                self, "잘못된 URL", "YouTube 영상 URL이 아닌 줄이 있습니다:\n" + "\n".join(invalid)
            )
            return
        if not valid:
            QMessageBox.warning(self, "필수 입력", "레퍼런스 URL을 1개 이상 입력해 주세요.")
            return
        if len(valid) > MAX_REFERENCE_URLS:
            QMessageBox.warning(
                self, "URL 개수 초과", f"레퍼런스 URL은 최대 {MAX_REFERENCE_URLS}개까지 입력할 수 있습니다."
            )
            return

        self._values = (name, valid)
        self.accept()

    def values(self) -> Tuple[str, List[str]]:
        return self._values


class TemplateReviewDialog(QDialog):
    def __init__(self, template: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"포맷 템플릿 검토 — {template.get('name', '')}")
        self.setMinimumSize(640, 720)
        self._template = template

        self._name = QLineEdit(template.get("name", ""))
        self._niche = QLineEdit(template.get("niche", ""))
        self._language = QLineEdit(template.get("language", ""))
        self._topic_angle = QPlainTextEdit(template.get("topic_angle", ""))
        self._hook_pattern = QPlainTextEdit(template.get("hook_pattern", ""))
        self._tone = QPlainTextEdit(template.get("tone", ""))
        self._visual_style = QPlainTextEdit(template.get("visual_style", ""))
        self._sentence_count = QSpinBox()
        self._sentence_count.setRange(SENTENCE_COUNT_MIN, SENTENCE_COUNT_MAX)
        self._sentence_count.setValue(int(template.get("sentence_count", SENTENCE_COUNT_MIN)))
        self._subtitle_color = QLineEdit(template.get("subtitle_color", ""))
        self._example_topics = QPlainTextEdit("\n".join(template.get("example_topics", [])))
        self._avoid = QPlainTextEdit("\n".join(template.get("avoid", [])))

        for editor in (self._topic_angle, self._hook_pattern, self._tone, self._visual_style):
            editor.setFixedHeight(60)

        sources = QLabel("\n".join(template.get("source_urls", [])))
        sources.setWordWrap(True)

        form = QFormLayout()
        form.addRow("이름", self._name)
        form.addRow("니치", self._niche)
        form.addRow("언어", self._language)
        form.addRow("주제 각도", self._topic_angle)
        form.addRow("훅 패턴", self._hook_pattern)
        form.addRow("말투", self._tone)
        form.addRow("비주얼 스타일", self._visual_style)
        form.addRow("문장 수", self._sentence_count)
        form.addRow("자막 색 (#RRGGBB)", self._subtitle_color)
        form.addRow("예시 주제 (줄 단위)", self._example_topics)
        form.addRow("금지 목록 (줄 단위)", self._avoid)
        form.addRow("레퍼런스", sources)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._result: Optional[dict] = None

    def _on_accept(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "필수 입력", "템플릿 이름을 입력해 주세요.")
            return
        color = self._subtitle_color.text().strip()
        if not HEX_COLOR.match(color):
            QMessageBox.warning(self, "자막 색", "자막 색은 #RRGGBB 형식이어야 합니다.")
            return

        result = dict(self._template)
        result.update(
            {
                "name": name,
                "niche": self._niche.text().strip(),
                "language": self._language.text().strip().lower(),
                "topic_angle": self._topic_angle.toPlainText().strip(),
                "hook_pattern": self._hook_pattern.toPlainText().strip(),
                "tone": self._tone.toPlainText().strip(),
                "visual_style": self._visual_style.toPlainText().strip(),
                "sentence_count": self._sentence_count.value(),
                "subtitle_color": color.upper(),
                "example_topics": _lines(self._example_topics.toPlainText()),
                "avoid": _lines(self._avoid.toPlainText()),
            }
        )
        self._result = result
        self.accept()

    def result_template(self) -> Optional[dict]:
        return self._result


def add_template_flow(parent: QWidget) -> bool:
    input_dialog = TemplateInputDialog(parent)
    if input_dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    name, urls = input_dialog.values()

    job = JobDialog(TemplateWorker(urls, name), f"템플릿 분석 — {name}", parent)
    job.exec()
    template = job.result()
    if not isinstance(template, dict):
        return False

    review = TemplateReviewDialog(template, parent)
    if review.exec() != QDialog.DialogCode.Accepted:
        return False
    add_template(review.result_template())
    return True


def edit_template_flow(parent: QWidget, row: dict) -> bool:
    template = get_template(row.get("id", ""))
    if template is None:
        QMessageBox.warning(parent, "템플릿 없음", "템플릿을 찾을 수 없습니다. 새로고침해 주세요.")
        return False

    review = TemplateReviewDialog(template, parent)
    if review.exec() != QDialog.DialogCode.Accepted:
        return False
    update_template(review.result_template())
    return True
```

- [ ] **Step 4: platforms.py 교체**

`src/ui/platforms.py` 전체를 다음으로 교체:

```python
"""
Platform spec — single source of truth for what the UI shows and edits.

Adding a new platform = add one Platform entry. The MainWindow reads from
this list to render the sidebar, the account list, and the add dialog.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from cache import (
    add_account,
    add_product,
    get_accounts,
    get_leads_cache_path,
    get_products,
    remove_account,
)
from templates import count_linked_accounts, get_templates, remove_template
from ui.template_dialog import add_template_flow, edit_template_flow


@dataclass
class FieldSpec:
    """One input field in the add-item dialog."""
    key: str
    label: str
    required: bool = True
    kind: str = "text"  # text | path | choice
    placeholder: str = ""
    choices_fn: Optional[Callable[[], List[tuple]]] = None  # [(label, value), ...] for kind="choice"


@dataclass
class Platform:
    """Metadata for a single sidebar entry."""
    key: str
    label: str
    item_label: str  # singular noun for buttons ("계정", "제품", "리드")

    list_fn: Callable[[], List[dict]]
    add_fn: Optional[Callable[[dict], None]]
    remove_fn: Optional[Callable[[str], None]]

    columns: List[tuple]  # [(header, dict_key), ...]
    fields: List[FieldSpec] = field(default_factory=list)

    # Optional hooks for platforms whose add/edit flow is not a simple form.
    custom_add: Optional[Callable[[Any], bool]] = None        # (parent) -> changed
    edit_fn: Optional[Callable[[Any, dict], bool]] = None     # (parent, row) -> changed
    remove_warning_fn: Optional[Callable[[str], str]] = None  # (item_id) -> extra warning


def _load_leads() -> List[dict]:
    path = get_leads_cache_path()
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("leads", [])
    return []


def template_choices() -> List[tuple]:
    return [("사용 안 함", "")] + [(t.get("name", ""), t.get("id", "")) for t in get_templates()]


def _youtube_rows() -> List[dict]:
    names = {t.get("id"): t.get("name", "") for t in get_templates()}
    return [
        {**account, "template_name": names.get(account.get("template_id"), "")}
        for account in get_accounts("youtube")
    ]


def _template_rows() -> List[dict]:
    return [{**t, "reference_count": len(t.get("source_urls", []))} for t in get_templates()]


def _template_remove_warning(template_id: str) -> str:
    linked = count_linked_accounts(template_id, get_accounts("youtube"))
    if not linked:
        return ""
    return f"이 템플릿에 연결된 YouTube 계정이 {linked}개 있습니다. 삭제하면 해당 계정은 니치 설정으로 생성합니다."


PLATFORMS: List[Platform] = [
    Platform(
        key="youtube",
        label="YouTube Shorts",
        item_label="계정",
        list_fn=_youtube_rows,
        add_fn=lambda data: add_account("youtube", data),
        remove_fn=lambda account_id: remove_account("youtube", account_id),
        columns=[
            ("닉네임", "nickname"),
            ("니치", "niche"),
            ("언어", "language"),
            ("템플릿", "template_name"),
            ("UUID", "id"),
        ],
        fields=[
            FieldSpec("nickname", "닉네임"),
            FieldSpec("browser_profile", "Chrome 프로필 경로", kind="path"),
            FieldSpec("niche", "니치"),
            FieldSpec("language", "언어", placeholder="korean"),
            FieldSpec(
                "template_id",
                "포맷 템플릿",
                required=False,
                kind="choice",
                choices_fn=template_choices,
            ),
        ],
    ),
    Platform(
        key="templates",
        label="포맷 템플릿",
        item_label="템플릿",
        list_fn=_template_rows,
        add_fn=None,
        remove_fn=remove_template,
        columns=[
            ("이름", "name"),
            ("니치", "niche"),
            ("언어", "language"),
            ("레퍼런스", "reference_count"),
            ("ID", "id"),
        ],
        custom_add=add_template_flow,
        edit_fn=edit_template_flow,
        remove_warning_fn=_template_remove_warning,
    ),
    Platform(
        key="twitter",
        label="Twitter / X",
        item_label="계정",
        list_fn=lambda: get_accounts("twitter"),
        add_fn=lambda data: add_account("twitter", data),
        remove_fn=lambda account_id: remove_account("twitter", account_id),
        columns=[
            ("닉네임", "nickname"),
            ("주제", "topic"),
            ("UUID", "id"),
        ],
        fields=[
            FieldSpec("nickname", "닉네임"),
            FieldSpec("browser_profile", "Chrome 프로필 경로", kind="path"),
            FieldSpec("topic", "주제"),
        ],
    ),
    Platform(
        key="affiliate",
        label="Affiliate Marketing",
        item_label="제품",
        list_fn=get_products,
        add_fn=add_product,
        remove_fn=None,  # cache.py has no remove_product yet
        columns=[
            ("Affiliate Link", "affiliate_link"),
            ("Twitter UUID", "twitter_uuid"),
            ("ID", "id"),
        ],
        fields=[
            FieldSpec("affiliate_link", "Affiliate 링크"),
            FieldSpec("twitter_uuid", "Twitter 계정 UUID"),
        ],
    ),
    Platform(
        key="leads",
        label="Local Leads",
        item_label="리드",
        list_fn=_load_leads,
        add_fn=None,  # leads are populated by LeadScraper, not the UI
        remove_fn=None,
        columns=[
            ("회사명", "company_name"),
            ("전화번호", "phone"),
            ("니치", "niche"),
        ],
        fields=[],
    ),
]


def find_platform(key: str) -> Optional[Platform]:
    return next((p for p in PLATFORMS if p.key == key), None)
```

- [ ] **Step 5: account_dialog.py 교체**

`src/ui/account_dialog.py` 전체를 다음으로 교체:

```python
"""
Add-item dialog. Renders one input row per FieldSpec. Returns a dict matching
the platform's field keys, with a fresh UUID injected as `id`.
"""

from uuid import uuid4

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.platforms import Platform


class AccountDialog(QDialog):
    def __init__(self, platform: Platform, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{platform.label} — 새 {platform.item_label}")
        self._platform = platform
        self._inputs: dict[str, QLineEdit | QComboBox] = {}

        form = QFormLayout()
        for spec in platform.fields:
            if spec.kind == "choice":
                combo = QComboBox()
                for label, value in (spec.choices_fn() if spec.choices_fn else []):
                    combo.addItem(label, value)
                form.addRow(spec.label, combo)
                self._inputs[spec.key] = combo
                continue

            line = QLineEdit()
            line.setPlaceholderText(spec.placeholder)

            if spec.kind == "path":
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                browse = QPushButton("찾아보기...")
                browse.clicked.connect(lambda _=False, le=line: self._pick_directory(le))
                row_layout.addWidget(line)
                row_layout.addWidget(browse)
                form.addRow(spec.label, row)
            else:
                form.addRow(spec.label, line)

            self._inputs[spec.key] = line

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._payload: dict | None = None

    @staticmethod
    def _pick_directory(line: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(line, "프로필 디렉토리 선택")
        if path:
            line.setText(path)

    def _on_accept(self) -> None:
        payload: dict = {"id": str(uuid4())}

        for spec in self._platform.fields:
            widget = self._inputs[spec.key]
            if isinstance(widget, QComboBox):
                value = str(widget.currentData() or "")
            else:
                value = widget.text().strip()
            if spec.required and not value:
                QMessageBox.warning(self, "필수 입력", f"'{spec.label}' 값을 입력해 주세요.")
                return
            payload[spec.key] = value

        if self._platform.key == "youtube":
            payload.setdefault("videos", [])
        if self._platform.key == "twitter":
            payload.setdefault("posts", [])

        self._payload = payload
        self.accept()

    def payload(self) -> dict | None:
        return self._payload
```

- [ ] **Step 6: main_window.py 수정**

(a) import 블록의 PySide6 위젯 목록에 `QInputDialog` 추가, 그리고 cache import 추가:

```python
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from cache import update_account
from ui.account_dialog import AccountDialog
from ui.job_dialog import JobDialog
from ui.model_picker import ensure_model_selected
from ui.platforms import PLATFORMS, Platform, template_choices
from ui.workers import UploadWorker, VideoWorker
```

(b) `_build_content`에서 `self._run_action` 등록 줄(`self._toolbar.addAction(self._run_action)`) 바로 아래에 추가:

```python

        self._link_action = QAction("템플릿 연결", self)
        self._link_action.triggered.connect(self._on_link_template)
        self._toolbar.addAction(self._link_action)
```

(c) `_reload_table` 끝의 액션 활성화 4줄을 교체:

```python
        self._add_action.setEnabled(platform.add_fn is not None or platform.custom_add is not None)
        self._remove_action.setEnabled(platform.remove_fn is not None)
        self._run_action.setEnabled(platform.key == "youtube")
        self._link_action.setEnabled(platform.key == "youtube")
        self._count_label.setText(f"  {len(rows)}개의 {platform.item_label}")
```

(d) `_on_add` 전체를 교체:

```python
    def _on_add(self) -> None:
        platform = self._current_platform
        if platform.custom_add is not None:
            if platform.custom_add(self):
                self._reload_table()
            return
        if platform.add_fn is None:
            return

        dialog = AccountDialog(platform, self)
        if dialog.exec() == AccountDialog.DialogCode.Accepted:
            payload = dialog.payload()
            if payload is not None:
                platform.add_fn(payload)
                self._reload_table()
```

(e) `_on_remove`의 `confirm = QMessageBox.question(...)` 호출을 교체:

```python
        message = f"이 {platform.item_label}을(를) 삭제할까요?"
        if platform.remove_warning_fn is not None:
            extra = platform.remove_warning_fn(item_id)
            if extra:
                message = f"{extra}\n\n{message}"
        confirm = QMessageBox.question(self, "삭제 확인", message)
```

(f) `_on_table_double_click`과 `_selected_account`를 교체하고, `_on_run` 안의 `account = self._selected_account()`를 `account = self._selected_row()`로 바꾼다:

```python
    def _on_table_double_click(self, _index) -> None:
        platform = self._current_platform
        if platform.key == "youtube":
            self._on_run()
            return
        if platform.edit_fn is not None:
            row = self._selected_row()
            if row is not None and platform.edit_fn(self, row):
                self._reload_table()

    def _selected_row(self) -> dict | None:
        platform = self._current_platform
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        item_id = item.data(Qt.ItemDataRole.UserRole) if item else ""
        for entry in platform.list_fn():
            if entry.get("id") == item_id:
                return entry
        return None
```

(g) `_on_run` 메서드 뒤에 추가:

```python

    def _on_link_template(self) -> None:
        if self._current_platform.key != "youtube":
            return
        account = self._selected_row()
        if account is None:
            QMessageBox.information(self, "선택 필요", "먼저 계정을 선택해 주세요.")
            return

        choices = template_choices()
        labels = [label for label, _ in choices]
        current = next(
            (i for i, (_, value) in enumerate(choices) if value == account.get("template_id", "")), 0
        )
        label, ok = QInputDialog.getItem(
            self, "템플릿 연결", f"{account.get('nickname', '')} 계정의 포맷 템플릿", labels, current, False
        )
        if not ok:
            return

        template_id = choices[labels.index(label)][1]
        update_account("youtube", account["id"], {"template_id": template_id})
        self._reload_table()
```

- [ ] **Step 7: 통과 확인 (전체)**

Run: `venv/bin/python -m pytest -v`
Expected: 모든 테스트 통과 (`77 passed`)

- [ ] **Step 8: 앱 기동 스모크**

Run: `QT_QPA_PLATFORM=offscreen venv/bin/python -c "import sys; sys.path.insert(0, 'src'); from PySide6.QtWidgets import QApplication; from ui.main_window import MainWindow; app = QApplication([]); w = MainWindow(); w._sidebar.setCurrentRow(1); print(w._table.columnCount(), w._add_action.isEnabled())"`
Expected: `5 True` (템플릿 플랫폼 컬럼 5개, 추가 버튼 활성)

- [ ] **Step 9: Commit**

```bash
git add src/ui/template_dialog.py src/ui/platforms.py src/ui/account_dialog.py src/ui/main_window.py tests/test_template_ui.py
git commit -m "Add format template management UI and account linking"
```

---

### Task 10: 설정 문서화와 수동 E2E

**Files:**
- Modify: `config.example.json`
- Modify: `docs/Configuration.md`
- Modify: `docs/superpowers/specs/2026-09-14-reference-format-templates-design.md` (구현 중 확정된 사항 반영)

**Interfaces:**
- Consumes: Task 0~9 전체
- Produces: 없음

- [ ] **Step 1: config.example.json**

`"tts_voice": "Jasper",` 줄을 다음으로 교체:

```json
  "tts_provider": "kittentts",
  "tts_voice": "Jasper",
  "gemini_tts_model": "gemini-3.1-flash-tts-preview",
  "gemini_tts_voice": "Kore",
  "reference_analysis_model": "gemini-3.8-flash",
```

Run: `venv/bin/python -c "import json; json.load(open('config.example.json')); print('valid')"`
Expected: `valid`

- [ ] **Step 2: docs/Configuration.md**

`- \`tts_voice\`: KittenTTS 음성 이름` 줄을 다음으로 교체:

```markdown
- `tts_provider`: `kittentts`(영어 전용, 로컬) 또는 `gemini`(한국어 포함 다국어, Gemini API 키 필요)
- `tts_voice`: KittenTTS 음성 이름
- `gemini_tts_model`: Gemini TTS 모델명
- `gemini_tts_voice`: Gemini TTS 프리셋 음성 이름 (예: `Kore`, `Puck`, `Charon`)
- `reference_analysis_model`: 포맷 템플릿용 레퍼런스 영상 분석·합성 모델명
```

`## 메모` 섹션 끝에 추가:

```markdown
- 포맷 템플릿 분석과 Gemini TTS는 `nanobanana2_api_key`(또는 `GEMINI_API_KEY`)를 함께 사용합니다.
- 레퍼런스 분석은 공개 YouTube 영상만 가능하며, 영상 파일은 내려받지 않습니다.
- 한국어 계정은 자막 인식률을 위해 `whisper_model`을 `small` 이상으로 설정하는 것을 권장합니다.
- 템플릿이 연결된 계정은 템플릿의 문장 수가 `script_sentence_length`보다 우선합니다.
```

- [ ] **Step 3: 스펙 문서에 확정 사항 반영**

스펙 6절 표의 기본값을 `reference_analysis_model=gemini-3.8-flash`, `gemini_tts_model=gemini-3.1-flash-tts-preview`, `gemini_tts_voice=Kore`로 고친다. 4.1절 표에 `src/gemini_client.py`, `src/gemini_tts.py`, `src/cache.py`(`update_account`), `src/cron.py`(템플릿 로드), main_window의 "템플릿 연결" 액션을 추가한다. 10절의 "Gemini TTS 실패" 행을 "2회 재시도 후 작업 실패 (KittenTTS로 대체하지 않음)"로 고친다. 7절 첫 문장의 "현재 프롬프트 문자열과 동일한 결과"를 "템플릿 전용 지시가 없는 기존 프롬프트"로 고친다.

- [ ] **Step 4: 전체 테스트 최종 확인**

Run: `venv/bin/python -m pytest -q`
Expected: `77 passed`

- [ ] **Step 5: 수동 E2E (운영자와 함께)**

전제: `config.json`에 Gemini 키, `tts_provider: "gemini"`, Ollama 모델, `Songs/` 음원이 준비됨.

1. `venv/bin/python src/main.py` 실행
2. 사이드바 "포맷 템플릿" → "+ 추가" → 이름 입력, 실제 공개 쇼츠 URL 2개 입력 → 확인
3. 분석 진행률이 "레퍼런스 분석 중 (1/2)" → "(2/2)" → "템플릿 합성 중" → "완료"로 진행되는지 확인
4. 검토 창에서 필드가 채워졌는지, `금지 목록`에 레퍼런스 주제가 들어갔는지 확인 → 저장
5. "YouTube Shorts"에서 계정 선택 → "템플릿 연결" → 방금 만든 템플릿 선택 → 표의 "템플릿" 컬럼 확인
6. "▶ 영상 생성" → 로그에 `포맷 템플릿: <이름>`, `TTS 제공자: gemini` 표시 확인 → 업로드 질문에서 "No"
7. 결과 영상에서 확인: 주제가 금지 목록과 다름 / 자막 색이 템플릿 값 / 한국어 내레이션 / 문장 수가 템플릿 값과 비슷함
8. 템플릿 삭제 시 "연결된 YouTube 계정이 1개" 경고가 뜨는지 확인 (취소)

Expected: 1~8 모두 확인. 실패 항목이 있으면 해당 단계와 로그를 기록해 보고한다 (완료로 처리하지 않는다).

- [ ] **Step 6: Commit**

```bash
git add config.example.json docs/Configuration.md docs/superpowers/specs/2026-09-14-reference-format-templates-design.md
git commit -m "Document format template and Gemini TTS configuration"
```
