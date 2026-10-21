"""Authenticated OpenRouter transport for text, images, speech and analysis."""

import json
import re

import requests

from config import get_openrouter_api_key, get_openrouter_base_url


class OpenRouterError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code

    @property
    def retryable(self) -> bool:
        return self.status_code is None or self.status_code == 429 or self.status_code >= 500


def _post(path: str, payload: dict, timeout: int = 300):
    key = get_openrouter_api_key()
    if not key:
        raise OpenRouterError("OpenRouter API 키가 없습니다 (OPENROUTER_API_KEY).", 401)
    base = get_openrouter_base_url().rstrip("/")
    base = base if base.endswith("/v1") else f"{base}/v1"
    try:
        response = requests.post(
            f"{base}/{path}",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        # Exceptions and provider bodies may contain prompts, URLs or credentials.
        raise OpenRouterError(f"OpenRouter 요청 실패 ({type(exc).__name__}).") from None
    if response.status_code != 200:
        raise OpenRouterError(f"OpenRouter HTTP {response.status_code}.", response.status_code)
    return response


def post_json(path: str, payload: dict, timeout: int = 300) -> dict:
    response = _post(path, payload, timeout)
    try:
        body = response.json()
    except ValueError:
        raise OpenRouterError("OpenRouter 응답이 JSON이 아닙니다.") from None
    if not isinstance(body, dict):
        raise OpenRouterError("OpenRouter 응답이 JSON 객체가 아닙니다.")
    if body.get("error"):
        code = body["error"].get("code") if isinstance(body["error"], dict) else None
        raise OpenRouterError("OpenRouter가 오류 응답을 반환했습니다.", code if isinstance(code, int) else None)
    return body


def post_audio(payload: dict, timeout: int = 300) -> bytes:
    response = _post("audio/speech", payload, timeout)
    if not response.headers.get("Content-Type", "").lower().startswith("audio/") or not response.content:
        raise OpenRouterError("OpenRouter 응답에 오디오가 없습니다.")
    return response.content


def generate_content(model: str, payload: dict, timeout: int = 300) -> dict:
    return post_json("chat/completions", {**payload, "model": model}, timeout)


def response_text(body: dict) -> str:
    choices = body.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        raise OpenRouterError("OpenRouter 응답에 텍스트가 없습니다.")
    content = (choices[0].get("message") or {}).get("content")
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    if not isinstance(content, str) or not content.strip():
        raise OpenRouterError("OpenRouter 응답에 텍스트가 없습니다.")
    return content


def parse_json_text(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        raise OpenRouterError("JSON 파싱 실패.") from None
    if not isinstance(parsed, dict):
        raise OpenRouterError("JSON 객체가 아닌 응답입니다.")
    return parsed


def json_response_format(schema: dict, name: str = "result") -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": True,
            "schema": {**schema, "additionalProperties": False},
        },
    }
