import pytest

import templates
from templates import (
    SENTENCE_COUNT_MAX,
    SENTENCE_COUNT_MIN,
    add_template,
    aggregate_sentence_counts,
    collect_avoid,
    count_linked_accounts,
    get_template,
    get_templates,
    load_account_template,
    merge_numeric,
    remove_template,
    update_template,
)


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = tmp_path / "templates.json"
    monkeypatch.setattr(templates, "get_templates_path", lambda: str(path))
    return path


def test_store_roundtrip(store):
    assert get_templates() == []
    add_template({"id": "t1", "name": "A"})
    add_template({"id": "t2", "name": "B"})

    assert [t["id"] for t in get_templates()] == ["t1", "t2"]
    assert get_template("t2")["name"] == "B"
    assert get_template("missing") is None
    assert get_template("") is None
    assert get_template(None) is None


def test_update_and_remove(store):
    add_template({"id": "t1", "name": "A"})
    update_template({"id": "t1", "name": "A2"})
    assert get_template("t1")["name"] == "A2"

    with pytest.raises(KeyError):
        update_template({"id": "nope", "name": "x"})

    remove_template("t1")
    assert get_templates() == []


def test_get_templates_tolerates_corrupt_file(store):
    store.write_text("{not json", encoding="utf-8")
    assert get_templates() == []


def test_aggregate_sentence_counts_median():
    assert aggregate_sentence_counts([5]) == 5
    assert aggregate_sentence_counts([4, 6, 9]) == 6
    assert aggregate_sentence_counts([4, 6]) == 5


def test_merge_numeric_single_analysis(analysis_factory):
    merged = merge_numeric([analysis_factory(sentence_count=7, subtitle_color="#ffffff", language="Korean")])
    assert merged == {"sentence_count": 7, "subtitle_color": "#FFFFFF", "language": "korean"}


def test_merge_numeric_clamps_sentence_count(analysis_factory):
    assert merge_numeric([analysis_factory(sentence_count=1)])["sentence_count"] == SENTENCE_COUNT_MIN
    assert merge_numeric([analysis_factory(sentence_count=30)])["sentence_count"] == SENTENCE_COUNT_MAX


def test_merge_numeric_color_and_language_votes(analysis_factory):
    analyses = [
        analysis_factory(subtitle_color="#FFFF00", language="korean"),
        analysis_factory(subtitle_color="#FFFFFF", language="english"),
        analysis_factory(subtitle_color="yellow", language="korean"),
    ]
    merged = merge_numeric(analyses)
    assert merged["subtitle_color"] == "#FFFF00"
    assert merged["language"] == "korean"


def test_merge_numeric_defaults_when_values_invalid(analysis_factory):
    merged = merge_numeric([analysis_factory(sentence_count="many", subtitle_color="red", language="")])
    assert merged == {"sentence_count": 4, "subtitle_color": "#FFFF00", "language": ""}


def test_collect_avoid_normalizes_and_dedupes(analysis_factory):
    analyses = [
        analysis_factory(topic="Coffee  after lunch", hook_text="Stop now."),
        analysis_factory(topic="Coffee after lunch", hook_text=""),
    ]
    assert collect_avoid(analyses) == ["Coffee after lunch", "Stop now."]


def test_load_account_template(store):
    add_template({"id": "t1", "name": "A"})

    assert load_account_template({"id": "a"}) == (None, None)
    assert load_account_template({"template_id": "t1"}) == ({"id": "t1", "name": "A"}, None)

    template, warning = load_account_template({"template_id": "gone"})
    assert template is None
    assert "gone" in warning


def test_count_linked_accounts():
    accounts = [{"template_id": "t1"}, {"template_id": "t2"}, {"template_id": "t1"}, {}]
    assert count_linked_accounts("t1", accounts) == 2
    assert count_linked_accounts("t9", accounts) == 0
