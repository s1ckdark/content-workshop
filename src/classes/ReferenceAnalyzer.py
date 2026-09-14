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
