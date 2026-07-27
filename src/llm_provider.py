import ollama
import requests
import re

from config import get_llm_api_key, get_llm_base_url, get_llm_provider

OPENAI_COMPATIBLE_PROVIDERS = {"lmstudio", "openai_compatible", "openai-compatible"}

_selected_model: str | None = None


def _provider() -> str:
    return get_llm_provider()


def _client() -> ollama.Client:
    return ollama.Client(host=get_llm_base_url())


def _openai_base_url() -> str:
    base_url = get_llm_base_url().rstrip("/")
    return base_url if base_url.endswith("/v1") else f"{base_url}/v1"


def _openai_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    api_key = get_llm_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _extract_openai_content(payload: dict) -> str:
    choices = payload.get("choices", [])
    if not choices:
        raise RuntimeError(f"No choices returned from LLM provider. Response: {payload}")

    message = choices[0].get("message", {})
    content = message.get("content", "")

    if isinstance(content, str):
        return _sanitize_text(content)

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return _sanitize_text("".join(parts))

    return _sanitize_text(str(content))


def _sanitize_text(text: str) -> str:
    cleaned = text.strip()

    # LM Studio hosted reasoning models may include hidden-thought blocks
    # in plain text responses. Strip them before downstream parsing.
    cleaned = re.sub(r"<think>.*?</think>\s*", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"^.*?</think>\s*", "", cleaned, flags=re.DOTALL | re.IGNORECASE)

    return cleaned.strip()


def list_models() -> list[str]:
    """
    Lists all models available on the configured LLM provider.

    Returns:
        models (list[str]): Sorted list of model names.
    """
    if _provider() in OPENAI_COMPATIBLE_PROVIDERS:
        response = requests.get(
            f"{_openai_base_url()}/models",
            headers=_openai_headers(),
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        return sorted(item.get("id", "") for item in payload.get("data", []) if item.get("id"))

    response = _client().list()
    return sorted(m.model for m in response.models)


def select_model(model: str) -> None:
    """
    Sets the model to use for all subsequent generate_text calls.

    Args:
        model (str): A provider-specific model name.
    """
    global _selected_model
    _selected_model = model


def get_active_model() -> str | None:
    """
    Returns the currently selected model, or None if none has been selected.
    """
    return _selected_model


def generate_text(prompt: str, model_name: str = None) -> str:
    """
    Generates text using the configured LLM provider.

    Args:
        prompt (str): User prompt
        model_name (str): Optional model name override

    Returns:
        response (str): Generated text
    """
    model = model_name or _selected_model
    if not model:
        raise RuntimeError(
            "No LLM model selected. Call select_model() first or pass model_name."
        )

    if _provider() in OPENAI_COMPATIBLE_PROVIDERS:
        response = requests.post(
            f"{_openai_base_url()}/chat/completions",
            headers=_openai_headers(),
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=300,
        )
        response.raise_for_status()
        return _extract_openai_content(response.json())

    response = _client().chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )

    return _sanitize_text(response["message"]["content"])
