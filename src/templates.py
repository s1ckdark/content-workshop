"""
Format templates: reusable channel formats distilled from reference Shorts.
Stored in .mp/templates.json as {"templates": [...]}.
"""

import json
import os
from collections import Counter
from statistics import median
from typing import List, Optional, Tuple

from cache import get_cache_path, write_json_atomic
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
    return data.get("templates", [])


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
