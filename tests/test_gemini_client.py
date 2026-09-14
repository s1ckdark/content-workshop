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


def test_generate_content_wraps_non_json_body(fake_post):
    class NonJsonResponse:
        status_code = 200
        text = "<html>not json</html>"

        def json(self):
            raise ValueError("no JSON object could be decoded")

    fake_post.queue.append(NonJsonResponse())

    with pytest.raises(GeminiError, match="JSON이 아닙니다"):
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
