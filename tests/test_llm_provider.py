"""Offline provider and credential-routing regression tests."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import config
import llm_provider


class LlmProviderTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {
            "llm_provider": "openrouter",
            "llm_model": "google/gemini-2.5-flash",
            "ollama_model": "local-only-model",
        }
        self.enterContext(patch.object(config, "_CONFIG_CACHE", self.cfg))
        self.enterContext(patch.object(llm_provider, "_selected_model", None))
        self.enterContext(patch.dict(os.environ, {
            "OPENROUTER_API_KEY": "test-openrouter",
            "OPENAI_API_KEY": "test-openai",
            "LLM_API_KEY": "test-generic",
        }))

    def test_openrouter_defaults_and_dedicated_key(self):
        self.assertEqual(config.get_llm_base_url(), "https://openrouter.ai/api/v1")
        self.assertEqual(config.get_llm_api_key(), "test-openrouter")

    def test_openrouter_never_falls_back_to_another_provider_key(self):
        os.environ.pop("OPENROUTER_API_KEY")
        self.assertEqual(config.get_llm_api_key(), "")

    def test_explicit_key_has_precedence(self):
        self.cfg["llm_api_key"] = " explicit-test-key "
        self.assertEqual(config.get_llm_api_key(), "explicit-test-key")

    def test_local_provider_settings_remain_supported(self):
        self.cfg.update(llm_provider="lmstudio", llm_base_url="http://localhost:1234/v1/")
        self.assertEqual(config.get_llm_base_url(), "http://localhost:1234/v1")
        self.assertEqual(config.get_llm_api_key(), "test-openai")

    def test_ollama_model_fallback_is_provider_scoped(self):
        self.cfg["llm_model"] = ""
        self.assertEqual(config.get_llm_model(), "")
        self.cfg["llm_provider"] = "ollama"
        self.assertEqual(config.get_llm_model(), "local-only-model")
        self.assertEqual(config.get_llm_base_url(), "http://127.0.0.1:11434")

    @patch.object(llm_provider.requests, "post")
    def test_generation_uses_openrouter_and_configured_model(self, post):
        post.return_value.json.return_value = {
            "choices": [{"message": {"content": "한국어 대본"}}]
        }
        self.assertEqual(llm_provider.generate_text("대본을 써 주세요."), "한국어 대본")
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-openrouter")
        self.assertEqual(kwargs["json"]["model"], self.cfg["llm_model"])
        self.assertEqual(kwargs["json"]["messages"][0]["content"], "대본을 써 주세요.")

    @patch.object(llm_provider.requests, "post")
    def test_selected_and_explicit_models_override_config(self, post):
        post.return_value.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        llm_provider.select_model("selected-model")
        llm_provider.generate_text("hello")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "selected-model")
        llm_provider.generate_text("hello", model_name="explicit-model")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "explicit-model")

    @patch.object(llm_provider.requests, "get")
    @patch.object(llm_provider.requests, "post")
    def test_missing_key_fails_before_network(self, post, get):
        os.environ.pop("OPENROUTER_API_KEY")
        for operation in (lambda: llm_provider.generate_text("hello"), llm_provider.list_models):
            with self.assertRaisesRegex(RuntimeError, "OPENROUTER_API_KEY"):
                operation()
        get.assert_not_called()
        post.assert_not_called()

    @patch.object(llm_provider.requests, "get")
    def test_lists_openrouter_models(self, get):
        get.return_value.json.return_value = {"data": [{"id": "z/model"}, {"id": "a/model"}]}
        self.assertEqual(llm_provider.list_models(), ["a/model", "z/model"])
        self.assertEqual(get.call_args.args[0], "https://openrouter.ai/api/v1/models")
        self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], "Bearer test-openrouter")

    def test_unknown_provider_does_not_fall_back_to_ollama(self):
        self.cfg["llm_provider"] = "openroutr"
        with self.assertRaisesRegex(ValueError, "Unsupported llm_provider"):
            llm_provider.list_models()

    def test_null_content_does_not_become_a_script(self):
        with self.assertRaisesRegex(RuntimeError, "no text content"):
            llm_provider._extract_openai_content({"choices": [{"message": {"content": None}}]})

    @patch.object(llm_provider, "_client")
    def test_ollama_generation_still_uses_local_client(self, client):
        self.cfg.update(llm_provider="ollama", llm_model="")
        client.return_value.chat.return_value = {"message": {"content": " local answer "}}
        self.assertEqual(llm_provider.generate_text("hello"), "local answer")
        self.assertEqual(client.return_value.chat.call_args.kwargs["model"], "local-only-model")


if __name__ == "__main__":
    unittest.main()
