from prompts import (
    DEFAULT_SUBTITLE_COLOR,
    MAX_EXISTING_TITLES,
    apply_visual_style,
    build_script_prompt,
    build_topic_prompt,
    resolve_language,
    resolve_sentence_count,
    resolve_subtitle_color,
    resolve_tts_style,
)

TEMPLATE = {
    "niche": "everyday money habits",
    "topic_angle": "hidden losses in daily routines",
    "hook_pattern": "open with a contrarian command",
    "tone": "fast, blunt, informal",
    "language": "korean",
    "sentence_count": 6,
    "visual_style": "bold flat illustration",
    "subtitle_color": "#00FF00",
    "example_topics": ["Why subscriptions drain you"],
    "avoid": ["Stop drinking coffee right after lunch."],
}


def test_topic_prompt_without_template_is_legacy():
    prompt = build_topic_prompt("cooking", None, ["Old title"])
    assert prompt == (
        "Please generate a specific video idea that takes about the following topic: cooking. "
        "Make it exactly one sentence. Only return the topic, nothing else."
    )


def test_topic_prompt_with_template_includes_constraints():
    prompt = build_topic_prompt("fallback niche", TEMPLATE, ["Old title A", "Old title B"])
    assert "everyday money habits" in prompt
    assert "hidden losses in daily routines" in prompt
    assert "Why subscriptions drain you" in prompt
    assert "Stop drinking coffee right after lunch." in prompt
    assert "Old title A" in prompt and "Old title B" in prompt
    assert "fallback niche" not in prompt


def test_topic_prompt_uses_account_niche_when_template_niche_empty():
    prompt = build_topic_prompt("fallback niche", {**TEMPLATE, "niche": ""}, [])
    assert "fallback niche" in prompt


def test_topic_prompt_keeps_only_recent_titles():
    titles = [f"title-{i}" for i in range(MAX_EXISTING_TITLES + 5)]
    prompt = build_topic_prompt("n", TEMPLATE, titles)
    assert "title-4\n" not in prompt
    assert f"title-{MAX_EXISTING_TITLES + 4}" in prompt


def test_script_prompt_without_template_has_no_template_directives():
    prompt = build_script_prompt("Subject X", "english", 4, None)
    assert "Generate a script for a video in 4 sentences" in prompt
    assert "Subject: Subject X" in prompt
    assert "Language: english" in prompt
    assert "HOOK PATTERN" not in prompt
    assert "TONE:" not in prompt


def test_script_prompt_with_template_adds_hook_tone_and_avoid():
    prompt = build_script_prompt("Subject X", "korean", 6, TEMPLATE)
    assert "Generate a script for a video in 6 sentences" in prompt
    assert "HOOK PATTERN: open with a contrarian command" in prompt
    assert "TONE: fast, blunt, informal" in prompt
    assert "Stop drinking coffee right after lunch." in prompt


def test_apply_visual_style_appends_suffix_to_strings_only():
    assert apply_visual_style(["a cat", 3], TEMPLATE) == ["a cat, bold flat illustration", 3]
    assert apply_visual_style(["a cat"], None) == ["a cat"]
    assert apply_visual_style(["a cat"], {**TEMPLATE, "visual_style": " "}) == ["a cat"]


def test_resolvers():
    assert resolve_language("english", TEMPLATE) == "english"
    assert resolve_language("", TEMPLATE) == "korean"
    assert resolve_language("", None) == ""
    assert resolve_sentence_count(4, TEMPLATE) == 6
    assert resolve_sentence_count(4, None) == 4
    assert resolve_sentence_count(4, {"sentence_count": 0}) == 4
    assert resolve_subtitle_color(TEMPLATE) == "#00FF00"
    assert resolve_subtitle_color({"subtitle_color": "yellow"}) == DEFAULT_SUBTITLE_COLOR
    assert resolve_subtitle_color(None) == DEFAULT_SUBTITLE_COLOR
    assert resolve_tts_style(TEMPLATE) == "fast, blunt, informal"
    assert resolve_tts_style({"tone": "  "}) is None
    assert resolve_tts_style(None) is None
