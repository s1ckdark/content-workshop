from classes.YouTube import YouTube

TEMPLATE = {
    "id": "t1",
    "name": "money",
    "niche": "everyday money habits",
    "topic_angle": "hidden losses",
    "hook_pattern": "contrarian command",
    "tone": "fast and blunt",
    "language": "korean",
    "sentence_count": 6,
    "visual_style": "bold flat illustration",
    "subtitle_color": "#00FF00",
    "example_topics": ["subscriptions"],
    "avoid": ["Stop drinking coffee right after lunch."],
}


def _bare_youtube(template, language=""):
    """Builds a YouTube instance without launching Chromium."""
    yt = YouTube.__new__(YouTube)
    yt._account_uuid = "acc"
    yt._niche = "account niche"
    yt._template = template
    yt._language = language or (template or {}).get("language", "")
    yt.images = []
    return yt


def test_generate_topic_uses_template_and_existing_titles(monkeypatch):
    yt = _bare_youtube(TEMPLATE)
    prompts = []
    monkeypatch.setattr(yt, "generate_response", lambda prompt, model_name=None: prompts.append(prompt) or "New topic")
    monkeypatch.setattr(yt, "get_videos", lambda: [{"title": "Old upload"}])

    assert yt.generate_topic() == "New topic"
    assert "Old upload" in prompts[0]
    assert "Stop drinking coffee right after lunch." in prompts[0]


def test_generate_topic_without_template_keeps_legacy_prompt(monkeypatch):
    yt = _bare_youtube(None, language="english")
    prompts = []
    monkeypatch.setattr(yt, "generate_response", lambda prompt, model_name=None: prompts.append(prompt) or "Topic")
    monkeypatch.setattr(yt, "get_videos", lambda: (_ for _ in ()).throw(AssertionError("must not read videos")))

    yt.generate_topic()

    assert prompts[0].startswith("Please generate a specific video idea that takes about the following topic: account niche.")


def test_generate_script_uses_template_sentence_count(monkeypatch):
    yt = _bare_youtube(TEMPLATE)
    yt.subject = "Subject"
    prompts = []
    monkeypatch.setattr(yt, "generate_response", lambda prompt, model_name=None: prompts.append(prompt) or "한 문장. 두 문장.")

    yt.generate_script()

    assert "in 6 sentences" in prompts[0]
    assert "HOOK PATTERN: contrarian command" in prompts[0]
    assert "Language: korean" in prompts[0]


def test_generate_script_to_speech_passes_template_tone(tmp_path):
    yt = _bare_youtube(TEMPLATE)
    yt.script = "안녕하세요. 반갑습니다!"
    captured = {}

    class FakeTTS:
        def synthesize(self, text, output_file, style=None):
            captured.update(text=text, style=style)
            return output_file

    yt.generate_script_to_speech(FakeTTS())

    assert captured["style"] == "fast and blunt"
    assert captured["text"] == "안녕하세요. 반갑습니다!"


def test_generate_script_to_speech_without_template_passes_no_style():
    yt = _bare_youtube(None, language="english")
    yt.script = "Hello."
    captured = {}

    class FakeTTS:
        def synthesize(self, text, output_file, style=None):
            captured["style"] = style
            return output_file

    yt.generate_script_to_speech(FakeTTS())

    assert captured["style"] is None
