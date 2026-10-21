"""Provider and media settings shared by the application and preflight."""

import os


OPENAI_COMPATIBLE_PROVIDERS = {
    "lmstudio", "openai_compatible", "openai-compatible", "openrouter"
}
SUPPORTED_PROVIDERS = OPENAI_COMPATIBLE_PROVIDERS | {"ollama"}
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_IMAGE_MODEL = "google/gemini-3.1-flash-image-preview"
DEFAULT_TTS_MODEL = "google/gemini-3.1-flash-tts-preview"
DEFAULT_REFERENCE_MODEL = "google/gemini-2.5-flash"
DEFAULT_STT_MODEL = "openai/whisper-1"


def provider(cfg: dict) -> str:
    return str(cfg.get("llm_provider") or "ollama").strip().lower()


def base_url(cfg: dict) -> str:
    configured = str(cfg.get("llm_base_url") or "").strip().rstrip("/")
    if configured:
        return configured
    if provider(cfg) == "openrouter":
        return OPENROUTER_BASE_URL
    return str(cfg.get("ollama_base_url") or "http://127.0.0.1:11434").rstrip("/")


def model(cfg: dict) -> str:
    configured = str(cfg.get("llm_model") or "").strip()
    if configured:
        return configured
    if provider(cfg) == "ollama":
        return str(cfg.get("ollama_model") or "").strip()
    return ""


def api_key(cfg: dict) -> str:
    configured = str(cfg.get("llm_api_key") or "").strip()
    if provider(cfg) == "openrouter":
        return openrouter_api_key(cfg)
    return (
        configured
        or os.environ.get("OPENAI_API_KEY", "").strip()
        or os.environ.get("LLM_API_KEY", "").strip()
    )


def openrouter_api_key(cfg: dict) -> str:
    configured = str(cfg.get("openrouter_api_key") or "").strip()
    if not configured and provider(cfg) == "openrouter":
        configured = str(cfg.get("llm_api_key") or "").strip()
    return configured or os.environ.get("OPENROUTER_API_KEY", "").strip()


def openrouter_base_url(cfg: dict) -> str:
    configured = str(cfg.get("openrouter_base_url") or "").strip().rstrip("/")
    if configured:
        return configured
    return base_url(cfg) if provider(cfg) == "openrouter" else OPENROUTER_BASE_URL


def _google_model(value: str) -> str:
    value = str(value).strip()
    return f"google/{value}" if value.startswith("gemini-") else value


def image_model(cfg: dict) -> str:
    return _google_model(cfg.get("image_model") or cfg.get("nanobanana2_model") or DEFAULT_IMAGE_MODEL)


def image_aspect_ratio(cfg: dict) -> str:
    return str(cfg.get("image_aspect_ratio") or cfg.get("nanobanana2_aspect_ratio") or "9:16")


def tts_model(cfg: dict) -> str:
    return _google_model(cfg.get("openrouter_tts_model") or cfg.get("gemini_tts_model") or DEFAULT_TTS_MODEL)


def tts_voice(cfg: dict) -> str:
    return str(cfg.get("openrouter_tts_voice") or cfg.get("gemini_tts_voice") or "Kore")


def reference_model(cfg: dict) -> str:
    return _google_model(cfg.get("reference_analysis_model") or DEFAULT_REFERENCE_MODEL)


def stt_model(cfg: dict) -> str:
    return str(cfg.get("openrouter_stt_model") or DEFAULT_STT_MODEL)
