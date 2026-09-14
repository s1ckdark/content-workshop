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

    try:
        return response.json()
    except ValueError as exc:
        raise GeminiError("Gemini 응답이 JSON이 아닙니다.") from exc


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
