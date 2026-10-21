#!/usr/bin/env python3
import json
import os
import sys

import requests


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT_DIR, "config.json")
sys.path.insert(0, os.path.join(ROOT_DIR, "src"))

import llm_settings


def ok(msg: str) -> None:
    print(f"[OK] {msg}")


def warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")


def check_llm(cfg: dict) -> bool:
    provider = llm_settings.provider(cfg)
    if provider not in llm_settings.SUPPORTED_PROVIDERS:
        fail(f"Unsupported llm_provider: {provider}")
        return False

    base = llm_settings.base_url(cfg)
    configured_model = llm_settings.model(cfg)
    headers = {}
    if provider in llm_settings.OPENAI_COMPATIBLE_PROVIDERS:
        base = base if base.endswith("/v1") else f"{base}/v1"
        key = llm_settings.api_key(cfg)
        if provider == "openrouter" and not key:
            fail("OpenRouter requires OPENROUTER_API_KEY or config.json llm_api_key.")
            return False
        if key:
            headers["Authorization"] = f"Bearer {key}"
        endpoint = f"{base}/models"
    else:
        endpoint = f"{base}/api/tags"

    try:
        if provider == "openrouter":
            # The model catalog alone does not prove the key is valid.
            auth = requests.get(f"{base}/key", headers=headers, timeout=15)
            if auth.status_code != 200:
                fail(f"OpenRouter authentication failed: HTTP {auth.status_code}")
                return False
            ok("OpenRouter API key authenticated")

        response = requests.get(endpoint, headers=headers, timeout=15)
        if response.status_code != 200:
            fail(f"{provider} model list failed: HTTP {response.status_code}")
            return False
        payload = response.json()
        if provider == "ollama":
            models = [m.get("name") for m in payload.get("models", []) if m.get("name")]
        else:
            models = [m.get("id") for m in payload.get("data", []) if m.get("id")]
    except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
        fail(f"{provider} check failed ({type(exc).__name__}). Check the endpoint and service.")
        return False

    if not models:
        fail(f"{provider} has no available models.")
        return False
    if configured_model and configured_model not in models:
        fail(f"Configured llm_model is not available on {provider}: {configured_model}")
        return False
    ok(f"llm_provider={provider}; {len(models)} models available")
    if configured_model:
        ok(f"llm_model={configured_model}")
    else:
        warn("llm_model is empty. Select a model in the app before generating content.")
    return True


def check_openrouter_media(cfg: dict) -> bool:
    key = llm_settings.openrouter_api_key(cfg)
    if not key:
        fail("Image, reference and audio tasks require OPENROUTER_API_KEY.")
        return False
    base = llm_settings.openrouter_base_url(cfg).rstrip("/")
    base = base if base.endswith("/v1") else f"{base}/v1"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        if llm_settings.provider(cfg) != "openrouter":
            auth = requests.get(f"{base}/key", headers=headers, timeout=15)
            if auth.status_code != 200:
                fail(f"OpenRouter authentication failed: HTTP {auth.status_code}")
                return False
        response = requests.get(
            f"{base}/models", headers=headers,
            params={"output_modalities": "all", "limit": 1000}, timeout=15,
        )
        if response.status_code != 200:
            fail(f"OpenRouter media catalog failed: HTTP {response.status_code}")
            return False
        catalog = {item["id"]: item for item in response.json().get("data", [])}
    except (requests.RequestException, ValueError, TypeError, KeyError, AttributeError) as exc:
        fail(f"OpenRouter media check failed ({type(exc).__name__}).")
        return False

    required = [
        ("image", llm_settings.image_model(cfg), "output_modalities", "image"),
        ("reference", llm_settings.reference_model(cfg), "input_modalities", "video"),
    ]
    tts_provider = str(cfg.get("tts_provider") or "openrouter").lower()
    stt_provider = str(cfg.get("stt_provider") or "openrouter").lower()
    if tts_provider in ("openrouter", "gemini"):
        required.append(("TTS", llm_settings.tts_model(cfg), "output_modalities", "speech"))
    elif tts_provider != "kittentts":
        fail(f"Unsupported tts_provider: {tts_provider}")
        return False
    if stt_provider == "openrouter":
        required.append(("STT", llm_settings.stt_model(cfg), "output_modalities", "transcription"))
    elif stt_provider != "local_whisper":
        fail(f"Unsupported stt_provider: {stt_provider}")
        return False
    valid = True
    for label, model, direction, modality in required:
        record = catalog.get(model, {})
        if modality not in record.get("architecture", {}).get(direction, []):
            fail(f"{label} model missing or incompatible: {model} (requires {modality})")
            valid = False
        else:
            ok(f"{label} model available: {model}")
    if tts_provider in ("openrouter", "gemini"):
        voices = catalog.get(llm_settings.tts_model(cfg), {}).get("supported_voices")
        if voices and llm_settings.tts_voice(cfg) not in voices:
            fail(f"TTS voice is not supported: {llm_settings.tts_voice(cfg)}")
            valid = False
    return valid


def main() -> int:
    if not os.path.exists(CONFIG_PATH):
        fail(f"Missing config file: {CONFIG_PATH}")
        return 1

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    failures = 0

    stt_provider = str(cfg.get("stt_provider", "openrouter")).lower()

    ok(f"stt_provider={stt_provider}")

    imagemagick_path = cfg.get("imagemagick_path", "")
    if imagemagick_path and os.path.exists(imagemagick_path):
        ok(f"imagemagick_path exists: {imagemagick_path}")
    else:
        warn(
            "imagemagick_path is not set to a valid executable path. "
            "MoviePy subtitle rendering may fail."
        )

    browser_profile = cfg.get("browser_profile") or cfg.get("firefox_profile", "")
    if browser_profile:
        if os.path.isdir(browser_profile):
            ok(f"browser_profile exists: {browser_profile}")
        else:
            warn(f"browser_profile does not exist: {browser_profile}")
    else:
        warn("browser_profile is empty. Twitter/YouTube automation requires this.")

    if not check_llm(cfg):
        failures += 1

    if not check_openrouter_media(cfg):
        failures += 1

    if stt_provider == "local_whisper":
        try:
            import faster_whisper  # noqa: F401

            ok("faster-whisper is installed")
        except Exception as exc:
            fail(f"faster-whisper is not importable: {exc}")
            failures += 1

    if failures:
        print("")
        print(f"Preflight completed with {failures} blocking issue(s).")
        return 1

    print("")
    print("Preflight passed. Credentials and model availability checked; generation and upload need separate verification.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
