"""
Format templates: reusable channel formats distilled from reference Shorts.
Stored in .mp/templates.json as {"templates": [...]}.
"""

import json
import os
from collections import Counter
from datetime import datetime
from statistics import median
from typing import Callable, List, Optional, Tuple
from uuid import uuid4

from cache import get_cache_path, write_json_atomic
from config import get_reference_analysis_model
from gemini_client import (
    GeminiError,
    generate_content,
    json_generation_config,
    parse_json_text,
    response_text,
)
from prompts import DEFAULT_SUBTITLE_COLOR, HEX_COLOR

SENTENCE_COUNT_MIN = 3
SENTENCE_COUNT_MAX = 12
DEFAULT_SENTENCE_COUNT = 4


# ------------------------------------------------------------------ storage
def get_templates_path() -> str:
    return os.path.join(get_cache_path(), "templates.json")


def get_templates() -> List[dict]:
    path = get_templates_path()
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            return []
    if not isinstance(data, dict):
        return []
    templates = data.get("templates", [])
    return templates if isinstance(templates, list) else []


def _save_templates(items: List[dict]) -> None:
    write_json_atomic(get_templates_path(), {"templates": items})


def get_template(template_id: Optional[str]) -> Optional[dict]:
    if not template_id:
        return None
    return next((t for t in get_templates() if t.get("id") == template_id), None)


def add_template(template: dict) -> None:
    items = get_templates()
    items.append(template)
    _save_templates(items)


def update_template(template: dict) -> None:
    items = get_templates()
    for index, existing in enumerate(items):
        if existing.get("id") == template.get("id"):
            items[index] = template
            _save_templates(items)
            return
    raise KeyError(template.get("id"))


def remove_template(template_id: str) -> None:
    _save_templates([t for t in get_templates() if t.get("id") != template_id])


# ---------------------------------------------------------- rule-based merge
def aggregate_sentence_counts(counts: List[int]) -> int:
    """
    Collapses per-reference sentence counts into one target count.

    Decision point: the median keeps the channel at the references' typical
    length. min() would favor the tightest reference; a duration-weighted
    mean would lean toward longer ones.
    """
    return int(round(median(counts)))


def merge_numeric(analyses: List[dict]) -> dict:
    counts = [
        a["sentence_count"]
        for a in analyses
        if isinstance(a.get("sentence_count"), int) and a["sentence_count"] > 0
    ]
    sentence_count = aggregate_sentence_counts(counts) if counts else DEFAULT_SENTENCE_COUNT
    sentence_count = max(SENTENCE_COUNT_MIN, min(SENTENCE_COUNT_MAX, sentence_count))

    colors = [
        str(a.get("subtitle_color", "")).upper()
        for a in analyses
        if HEX_COLOR.match(str(a.get("subtitle_color", "")))
    ]
    subtitle_color = Counter(colors).most_common(1)[0][0] if colors else DEFAULT_SUBTITLE_COLOR

    languages = [str(a.get("language", "")).strip().lower() for a in analyses]
    languages = [language for language in languages if language]
    language = Counter(languages).most_common(1)[0][0] if languages else ""

    return {"sentence_count": sentence_count, "subtitle_color": subtitle_color, "language": language}


def collect_avoid(analyses: List[dict]) -> List[str]:
    avoid: List[str] = []
    for analysis in analyses:
        for key in ("topic", "hook_text"):
            value = " ".join(str(analysis.get(key, "")).split())
            if value and value not in avoid:
                avoid.append(value)
    return avoid


# ---------------------------------------------------------- account linkage
def load_account_template(account: dict) -> Tuple[Optional[dict], Optional[str]]:
    template_id = (account or {}).get("template_id") or ""
    if not template_id:
        return None, None
    template = get_template(template_id)
    if template is None:
        return None, f"연결된 포맷 템플릿({template_id})을 찾을 수 없어 니치 설정으로 생성합니다."
    return template, None


def count_linked_accounts(template_id: str, accounts: List[dict]) -> int:
    return sum(1 for account in accounts if account.get("template_id") == template_id)


# ---------------------------------------------------------------- synthesis
TEXT_FIELDS = ("niche", "topic_angle", "hook_pattern", "tone", "visual_style")

SYNTHESIS_SCHEMA = {
    "type": "object",
    "properties": {
        "niche": {"type": "string", "description": "One-line channel niche summary."},
        "topic_angle": {"type": "string", "description": "How topics are chosen and framed."},
        "hook_pattern": {"type": "string", "description": "Instruction for writing the first sentence."},
        "tone": {"type": "string", "description": "Narration tone and pacing instruction."},
        "visual_style": {
            "type": "string",
            "description": "English image-prompt suffix describing the shared visual style.",
        },
        "example_topics": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 5,
            "maxItems": 5,
            "description": "New topics that fit the format and avoid the forbidden list.",
        },
    },
    "required": ["niche", "topic_angle", "hook_pattern", "tone", "visual_style", "example_topics"],
}


def build_synthesis_prompt(analyses: List[dict], avoid: List[str]) -> str:
    return (
        "You are designing a reusable YouTube Shorts format for a new channel.\n"
        "Below are structured analyses of reference Shorts the operator likes.\n"
        "Extract only what they have in common: format, hook style, tone, visual style and topic angle.\n"
        "Do NOT copy any concrete topic or line. example_topics must be new topics that fit the format "
        "and must not overlap with the forbidden list.\n"
        "Write niche, topic_angle, hook_pattern, tone and example_topics in the references' spoken language. "
        "Write visual_style in English.\n\n"
        f"Forbidden topics and lines:\n{json.dumps(avoid, ensure_ascii=False, indent=2)}\n\n"
        f"Reference analyses:\n{json.dumps(analyses, ensure_ascii=False, indent=2)}"
    )


def _valid_synthesis(data: dict) -> bool:
    return all(isinstance(data.get(key), str) for key in TEXT_FIELDS) and isinstance(
        data.get("example_topics"), list
    )


def synthesize(analyses: List[dict], name: str, retries: int = 1) -> dict:
    """
    Builds a template from per-reference analyses.

    Text fields come from one Gemini call (retried `retries` times on any
    Gemini error or schema mismatch); numeric fields and the avoid list are
    computed locally.
    """
    if not analyses:
        raise ValueError("분석 결과가 없습니다.")

    avoid = collect_avoid(analyses)
    payload = {
        "contents": [{"parts": [{"text": build_synthesis_prompt(analyses, avoid)}]}],
        "generationConfig": json_generation_config(SYNTHESIS_SCHEMA),
    }

    data: Optional[dict] = None
    last_error: GeminiError = GeminiError("합성 결과가 스키마와 맞지 않습니다.")
    for _ in range(retries + 1):
        try:
            candidate = parse_json_text(
                response_text(generate_content(get_reference_analysis_model(), payload))
            )
        except GeminiError as exc:
            last_error = exc
            continue
        if _valid_synthesis(candidate):
            data = candidate
            break
        last_error = GeminiError("합성 결과가 스키마와 맞지 않습니다.")
    if data is None:
        raise last_error

    template = {
        "id": str(uuid4()),
        "name": name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_urls": [analysis.get("url", "") for analysis in analyses],
    }
    template.update({key: data[key].strip() for key in TEXT_FIELDS})
    template["example_topics"] = [
        topic.strip() for topic in data["example_topics"] if isinstance(topic, str) and topic.strip()
    ]
    template.update(merge_numeric(analyses))
    template["avoid"] = avoid
    template["analyses"] = analyses
    return template


# ----------------------------------------------------------------- pipeline
class TemplateCancelled(Exception):
    """Raised when the operator cancels template creation."""


def run_template_pipeline(
    urls: List[str],
    name: str,
    analyze_fn: Callable[[str], dict],
    synthesize_fn: Callable[[List[dict], str], dict],
    on_progress: Callable[[str, int], None],
    is_cancelled: Callable[[], bool],
    on_failure: Optional[Callable[[str], None]] = None,
) -> Tuple[dict, List[str]]:
    """
    Analyzes every URL, skipping failures, then synthesizes one template.

    Returns:
        (template, failures): failures are human-readable "url — reason" lines.

    Raises:
        TemplateCancelled: Cancel requested between steps.
        RuntimeError: Every URL failed to analyze.
    """
    analyses: List[dict] = []
    failures: List[str] = []
    total = len(urls)

    for index, url in enumerate(urls, start=1):
        if is_cancelled():
            raise TemplateCancelled()
        on_progress(f"레퍼런스 분석 중 ({index}/{total})", int(5 + 80 * (index - 1) / total))
        try:
            analyses.append(analyze_fn(url))
        except Exception as exc:
            line = f"{url} — {exc}"
            failures.append(line)
            if on_failure is not None:
                on_failure(line)

    if not analyses:
        raise RuntimeError("모든 레퍼런스 분석에 실패했습니다:\n" + "\n".join(failures))

    if is_cancelled():
        raise TemplateCancelled()
    on_progress("템플릿 합성 중", 85)
    return synthesize_fn(analyses, name), failures
