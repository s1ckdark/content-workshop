"""Preflight must validate the selected provider without exposing secrets."""

import importlib.util
import io
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

PREFLIGHT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "preflight_local.py"
SPEC = importlib.util.spec_from_file_location("preflight_local", PREFLIGHT_PATH)
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


def response(status=200, payload=None):
    return Mock(status_code=status, json=Mock(return_value=payload or {}))


class PreflightLlmTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {"llm_provider": "openrouter", "llm_model": "provider/model"}
        self.enterContext(patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-openrouter"}))
        self.output = self.enterContext(redirect_stdout(io.StringIO()))
        self.get = self.enterContext(patch.object(preflight.requests, "get"))

    def test_openrouter_checks_key_and_configured_model(self):
        self.get.side_effect = [
            response(),
            response(payload={"data": [{"id": "provider/model"}]}),
        ]
        self.assertTrue(preflight.check_llm(self.cfg))
        self.assertEqual(
            [call.args[0] for call in self.get.call_args_list],
            ["https://openrouter.ai/api/v1/key", "https://openrouter.ai/api/v1/models"],
        )
        self.assertNotIn("test-openrouter", self.output.getvalue())

    def test_invalid_key_fails_before_public_model_catalog(self):
        self.get.return_value = response(401)
        self.assertFalse(preflight.check_llm(self.cfg))
        self.get.assert_called_once()
        self.assertIn("HTTP 401", self.output.getvalue())

    def test_missing_key_fails_without_network(self):
        os.environ.pop("OPENROUTER_API_KEY")
        self.assertFalse(preflight.check_llm(self.cfg))
        self.get.assert_not_called()

    def test_unknown_model_fails(self):
        self.get.side_effect = [response(), response(payload={"data": [{"id": "other/model"}]})]
        self.assertFalse(preflight.check_llm(self.cfg))
        self.assertIn("not available", self.output.getvalue())

    def test_lmstudio_checks_models_instead_of_ollama(self):
        self.cfg.update(llm_provider="lmstudio", llm_base_url="http://localhost:1234")
        self.get.return_value = response(payload={"data": [{"id": "provider/model"}]})
        self.assertTrue(preflight.check_llm(self.cfg))
        self.get.assert_called_once()
        self.assertEqual(self.get.call_args.args[0], "http://localhost:1234/v1/models")

    def test_ollama_uses_legacy_model_and_endpoint(self):
        self.cfg = {"ollama_model": "local-model"}
        self.get.return_value = response(payload={"models": [{"name": "local-model"}]})
        self.assertTrue(preflight.check_llm(self.cfg))
        self.assertEqual(self.get.call_args.args[0], "http://127.0.0.1:11434/api/tags")
        self.assertEqual(self.get.call_args.kwargs["headers"], {})

    def test_http_failure_cannot_pass_reachability(self):
        self.cfg["llm_provider"] = "lmstudio"
        self.get.return_value = response(500)
        self.assertFalse(preflight.check_llm(self.cfg))

    def test_connection_errors_do_not_print_credentials(self):
        self.get.side_effect = preflight.requests.ConnectionError("test-openrouter")
        self.assertFalse(preflight.check_llm(self.cfg))
        self.assertNotIn("test-openrouter", self.output.getvalue())

    def test_empty_catalog_fails(self):
        self.get.side_effect = [response(), response(payload={"data": []})]
        self.assertFalse(preflight.check_llm(self.cfg))

    def media_catalog(self):
        return [
            {"id": "google/gemini-3.1-flash-image-preview", "architecture": {"output_modalities": ["image"]}},
            {"id": "google/gemini-2.5-flash", "architecture": {"input_modalities": ["video"]}},
            {"id": "google/gemini-3.1-flash-tts-preview", "architecture": {"output_modalities": ["speech"]}, "supported_voices": ["Kore"]},
            {"id": "openai/whisper-1", "architecture": {"output_modalities": ["transcription"]}},
        ]

    def test_all_media_models_and_voice_are_checked(self):
        self.get.return_value = response(payload={"data": self.media_catalog()})
        self.assertTrue(preflight.check_openrouter_media(self.cfg))
        self.assertEqual(self.get.call_args.kwargs["params"]["output_modalities"], "all")
        self.assertEqual(self.get.call_args.kwargs["headers"]["Authorization"], "Bearer test-openrouter")

    def test_media_rejects_model_without_required_capability(self):
        catalog = self.media_catalog()
        catalog[0]["architecture"]["output_modalities"] = ["text"]
        self.get.return_value = response(payload={"data": catalog})
        self.assertFalse(preflight.check_openrouter_media(self.cfg))
        self.assertIn("requires image", self.output.getvalue())

    def test_media_rejects_unsupported_voice(self):
        self.cfg["openrouter_tts_voice"] = "Jasper"
        self.get.return_value = response(payload={"data": self.media_catalog()})
        self.assertFalse(preflight.check_openrouter_media(self.cfg))

    def test_media_does_not_accept_legacy_google_key(self):
        os.environ.pop("OPENROUTER_API_KEY")
        self.cfg["nanobanana2_api_key"] = "old-google-key"
        self.assertFalse(preflight.check_openrouter_media(self.cfg))
        self.get.assert_not_called()

    def test_unknown_stt_provider_fails_instead_of_local_fallback(self):
        self.cfg["stt_provider"] = "third_party_assemblyai"
        self.get.return_value = response(payload={"data": self.media_catalog()})
        self.assertFalse(preflight.check_openrouter_media(self.cfg))


if __name__ == "__main__":
    unittest.main()
