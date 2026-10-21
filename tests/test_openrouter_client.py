import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import config
import openrouter_client as client


class OpenRouterClientTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {
            "llm_provider": "openrouter", "llm_base_url": "https://example.test/api/v1",
            "llm_api_key": "test-openrouter",
            "nanobanana2_api_key": "unused-google-key",
        }
        self.enterContext(patch.object(config, "_CONFIG_CACHE", self.cfg))
        self.post = self.enterContext(patch.object(client.requests, "post"))
        self.post.return_value = Mock(
            status_code=200, headers={"Content-Type": "application/json"},
            json=Mock(return_value={"choices": [{"message": {"content": "hello"}}]}),
        )

    def test_chat_uses_bearer_and_openrouter_contract(self):
        body = client.generate_content("vendor/model", {"messages": []})
        self.assertEqual(client.response_text(body), "hello")
        self.assertEqual(self.post.call_args.args[0], "https://example.test/api/v1/chat/completions")
        self.assertEqual(self.post.call_args.kwargs["headers"]["Authorization"], "Bearer test-openrouter")
        self.assertNotIn("x-goog-api-key", self.post.call_args.kwargs["headers"])
        self.assertEqual(self.post.call_args.kwargs["json"]["model"], "vendor/model")

    def test_missing_key_never_uses_google_key(self):
        self.cfg["llm_api_key"] = ""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            with self.assertRaisesRegex(client.OpenRouterError, "API 키"):
                client.generate_content("model", {})
        self.post.assert_not_called()

    def test_http_error_omits_sensitive_response_body(self):
        self.post.return_value.status_code = 401
        self.post.return_value.text = "test-openrouter sensitive prompt"
        with self.assertRaises(client.OpenRouterError) as caught:
            client.generate_content("model", {})
        self.assertEqual(caught.exception.status_code, 401)
        self.assertFalse(caught.exception.retryable)
        self.assertNotIn("sensitive", str(caught.exception))
        self.assertNotIn("test-openrouter", str(caught.exception))

    def test_transient_errors_can_retry(self):
        for status in (429, 500, 503):
            self.assertTrue(client.OpenRouterError("error", status).retryable)

    def test_network_error_is_sanitized(self):
        self.post.side_effect = client.requests.ConnectionError("test-openrouter")
        with self.assertRaisesRegex(client.OpenRouterError, "요청 실패") as caught:
            client.generate_content("model", {})
        self.assertNotIn("test-openrouter", str(caught.exception))

    def test_non_json_body_fails(self):
        self.post.return_value.json.side_effect = ValueError("secret")
        with self.assertRaisesRegex(client.OpenRouterError, "JSON이 아닙니다"):
            client.generate_content("model", {})

    def test_http_200_error_body_fails(self):
        self.post.return_value.json.return_value = {"error": {"code": 402, "message": "private"}}
        with self.assertRaises(client.OpenRouterError) as caught:
            client.generate_content("model", {})
        self.assertFalse(caught.exception.retryable)

    def test_audio_endpoint_accepts_binary_only(self):
        response = self.post.return_value
        response.headers = {"Content-Type": "audio/mpeg"}
        response.content = b"encoded-audio"
        self.assertEqual(client.post_audio({"input": "hi"}), b"encoded-audio")
        self.assertTrue(self.post.call_args.args[0].endswith("/audio/speech"))
        response.headers = {"Content-Type": "application/json"}
        with self.assertRaisesRegex(client.OpenRouterError, "오디오"):
            client.post_audio({})

    def test_structured_response_and_json_validation(self):
        schema = {"type": "object", "properties": {"topic": {"type": "string"}}}
        result = client.json_response_format(schema)
        self.assertTrue(result["json_schema"]["strict"])
        self.assertFalse(result["json_schema"]["schema"]["additionalProperties"])
        self.assertNotIn("additionalProperties", schema)
        self.assertEqual(client.parse_json_text('```json\n{"a": 1}\n```'), {"a": 1})
        for text in ("oops", "[1]"):
            with self.assertRaises(client.OpenRouterError):
                client.parse_json_text(text)

    def test_empty_chat_text_fails(self):
        for body in ({}, {"choices": [{"message": {"content": None}}]}):
            with self.assertRaises(client.OpenRouterError):
                client.response_text(body)

    def test_media_config_defaults_and_legacy_model_names(self):
        self.assertEqual(config.get_tts_provider(), "openrouter")
        self.assertEqual(config.get_stt_provider(), "openrouter")
        self.assertEqual(config.get_openrouter_tts_voice(), "Kore")
        self.assertEqual(config.get_image_model(), "google/gemini-3.1-flash-image-preview")
        self.cfg.update(gemini_tts_model="gemini-3.1-flash-tts-preview", tts_provider="gemini")
        self.assertEqual(config.get_tts_provider(), "openrouter")
        self.assertEqual(config.get_openrouter_tts_model(), "google/gemini-3.1-flash-tts-preview")


if __name__ == "__main__":
    unittest.main()
