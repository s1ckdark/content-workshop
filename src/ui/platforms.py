"""
Platform spec — single source of truth for what the UI shows and edits.

Adding a new platform = add one Platform entry. The MainWindow reads from
this list to render the sidebar, the account list, and the add dialog.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from cache import (
    add_account,
    add_product,
    get_accounts,
    get_leads_cache_path,
    get_products,
    remove_account,
)


@dataclass
class FieldSpec:
    """One input field in the add-item dialog."""
    key: str
    label: str
    required: bool = True
    kind: str = "text"  # text | path
    placeholder: str = ""


@dataclass
class Platform:
    """Metadata for a single sidebar entry."""
    key: str
    label: str
    item_label: str  # singular noun for buttons ("계정", "제품", "리드")

    list_fn: Callable[[], List[dict]]
    add_fn: Optional[Callable[[dict], None]]
    remove_fn: Optional[Callable[[str], None]]

    columns: List[tuple]  # [(header, dict_key), ...]
    fields: List[FieldSpec] = field(default_factory=list)


def _load_leads() -> List[dict]:
    path = get_leads_cache_path()
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("leads", [])
    return []


PLATFORMS: List[Platform] = [
    Platform(
        key="youtube",
        label="YouTube Shorts",
        item_label="계정",
        list_fn=lambda: get_accounts("youtube"),
        add_fn=lambda data: add_account("youtube", data),
        remove_fn=lambda account_id: remove_account("youtube", account_id),
        columns=[
            ("닉네임", "nickname"),
            ("니치", "niche"),
            ("언어", "language"),
            ("UUID", "id"),
        ],
        fields=[
            FieldSpec("nickname", "닉네임"),
            FieldSpec("browser_profile", "Chrome 프로필 경로", kind="path"),
            FieldSpec("niche", "니치"),
            FieldSpec("language", "언어", placeholder="korean"),
        ],
    ),
    Platform(
        key="twitter",
        label="Twitter / X",
        item_label="계정",
        list_fn=lambda: get_accounts("twitter"),
        add_fn=lambda data: add_account("twitter", data),
        remove_fn=lambda account_id: remove_account("twitter", account_id),
        columns=[
            ("닉네임", "nickname"),
            ("주제", "topic"),
            ("UUID", "id"),
        ],
        fields=[
            FieldSpec("nickname", "닉네임"),
            FieldSpec("browser_profile", "Chrome 프로필 경로", kind="path"),
            FieldSpec("topic", "주제"),
        ],
    ),
    Platform(
        key="affiliate",
        label="Affiliate Marketing",
        item_label="제품",
        list_fn=get_products,
        add_fn=add_product,
        remove_fn=None,  # cache.py has no remove_product yet
        columns=[
            ("Affiliate Link", "affiliate_link"),
            ("Twitter UUID", "twitter_uuid"),
            ("ID", "id"),
        ],
        fields=[
            FieldSpec("affiliate_link", "Affiliate 링크"),
            FieldSpec("twitter_uuid", "Twitter 계정 UUID"),
        ],
    ),
    Platform(
        key="leads",
        label="Local Leads",
        item_label="리드",
        list_fn=_load_leads,
        add_fn=None,  # leads are populated by LeadScraper, not the UI
        remove_fn=None,
        columns=[
            ("회사명", "company_name"),
            ("전화번호", "phone"),
            ("니치", "niche"),
        ],
        fields=[],
    ),
]


def find_platform(key: str) -> Optional[Platform]:
    return next((p for p in PLATFORMS if p.key == key), None)
