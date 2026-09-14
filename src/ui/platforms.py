"""
Platform spec — single source of truth for what the UI shows and edits.

Adding a new platform = add one Platform entry. The MainWindow reads from
this list to render the sidebar, the account list, and the add dialog.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from cache import (
    add_account,
    add_product,
    get_accounts,
    get_leads_cache_path,
    get_products,
    remove_account,
)
from templates import count_linked_accounts, get_templates, remove_template
from ui.template_dialog import add_template_flow, edit_template_flow


@dataclass
class FieldSpec:
    """One input field in the add-item dialog."""
    key: str
    label: str
    required: bool = True
    kind: str = "text"  # text | path | choice
    placeholder: str = ""
    choices_fn: Optional[Callable[[], List[tuple]]] = None  # [(label, value), ...] for kind="choice"


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

    # Optional hooks for platforms whose add/edit flow is not a simple form.
    custom_add: Optional[Callable[[Any], bool]] = None        # (parent) -> changed
    edit_fn: Optional[Callable[[Any, dict], bool]] = None     # (parent, row) -> changed
    remove_warning_fn: Optional[Callable[[str], str]] = None  # (item_id) -> extra warning


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


def template_choices() -> List[tuple]:
    return [("사용 안 함", "")] + [(t.get("name", ""), t.get("id", "")) for t in get_templates()]


def unique_template_labels(templates: List[dict]) -> List[tuple]:
    """
    Pure label-building helper for the "템플릿 연결" dialog.

    QInputDialog.getItem returns only the chosen label text, so plain
    template names must stay unique there — otherwise two templates sharing
    a name (or a template literally named "사용 안 함") would resolve to the
    wrong id via a first-match label lookup. Every real template gets an id
    suffix so its label can never collide with another template's or with
    the unlink placeholder.
    """
    choices = [("사용 안 함", "")]
    for t in templates:
        template_id = t.get("id", "")
        choices.append((f"{t.get('name', '')} ({template_id[:8]})", template_id))
    return choices


def template_link_choices() -> List[tuple]:
    return unique_template_labels(get_templates())


def _youtube_rows() -> List[dict]:
    names = {t.get("id"): t.get("name", "") for t in get_templates()}
    return [
        {**account, "template_name": names.get(account.get("template_id"), "")}
        for account in get_accounts("youtube")
    ]


def _template_rows() -> List[dict]:
    return [{**t, "reference_count": len(t.get("source_urls", []))} for t in get_templates()]


def _template_remove_warning(template_id: str) -> str:
    linked = count_linked_accounts(template_id, get_accounts("youtube"))
    if not linked:
        return ""
    return f"이 템플릿에 연결된 YouTube 계정이 {linked}개 있습니다. 삭제하면 해당 계정은 니치 설정으로 생성합니다."


PLATFORMS: List[Platform] = [
    Platform(
        key="youtube",
        label="YouTube Shorts",
        item_label="계정",
        list_fn=_youtube_rows,
        add_fn=lambda data: add_account("youtube", data),
        remove_fn=lambda account_id: remove_account("youtube", account_id),
        columns=[
            ("닉네임", "nickname"),
            ("니치", "niche"),
            ("언어", "language"),
            ("템플릿", "template_name"),
            ("UUID", "id"),
        ],
        fields=[
            FieldSpec("nickname", "닉네임"),
            FieldSpec("browser_profile", "Chrome 프로필 경로", kind="path"),
            FieldSpec("niche", "니치"),
            FieldSpec("language", "언어", placeholder="korean"),
            FieldSpec(
                "template_id",
                "포맷 템플릿",
                required=False,
                kind="choice",
                choices_fn=template_choices,
            ),
        ],
    ),
    Platform(
        key="templates",
        label="포맷 템플릿",
        item_label="템플릿",
        list_fn=_template_rows,
        add_fn=None,
        remove_fn=remove_template,
        columns=[
            ("이름", "name"),
            ("니치", "niche"),
            ("언어", "language"),
            ("레퍼런스", "reference_count"),
            ("ID", "id"),
        ],
        custom_add=add_template_flow,
        edit_fn=edit_template_flow,
        remove_warning_fn=_template_remove_warning,
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
