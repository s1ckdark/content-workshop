import json

import pytest

from classes.ReferenceAnalyzer import (
    REQUIRED_KEYS,
    analyze,
    normalize_youtube_url,
    parse_url_lines,
)
from openrouter_client import OpenRouterError

VIDEO = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "raw",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch?v=dQw4w9WgXcQ&t=10s",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://youtube.com/shorts/dQw4w9WgXcQ?feature=share",
        "https://youtu.be/dQw4w9WgXcQ",
        "youtu.be/dQw4w9WgXcQ",
        "  https://www.youtube.com/shorts/dQw4w9WgXcQ  ",
    ],
)
def test_normalize_accepts_youtube_forms(raw):
    assert normalize_youtube_url(raw) == VIDEO


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "https://vimeo.com/123456",
        "https://www.youtube.com/watch?v=short",
        "https://www.youtube.com/shorts/",
        "https://www.youtube.com/channel/UC1234567890",
        "not a url",
    ],
)
def test_normalize_rejects_non_video_urls(raw):
    assert normalize_youtube_url(raw) is None


def test_parse_url_lines_splits_valid_invalid_and_dedupes():
    text = "\n".join(
        [
            "https://youtu.be/dQw4w9WgXcQ",
            "",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
            "https://vimeo.com/1",
        ]
    )
    valid, invalid = parse_url_lines(text)
    assert valid == [VIDEO]
    assert invalid == ["https://vimeo.com/1"]


def _analysis_json(analysis_factory, **overrides):
    data = analysis_factory(**overrides)
    data.pop("url")
    return json.dumps(data)


def test_analyze_sends_video_uri_and_returns_analysis(fake_post, analysis_factory):
    fake_post.queue.append(fake_post.Response(body=fake_post.text_body(_analysis_json(analysis_factory))))

    result = analyze("https://youtube.com/shorts/dQw4w9WgXcQ")

    call = fake_post.calls[0]
    assert call["url"].endswith("/chat/completions")
    assert call["json"]["model"] == "analysis-model"
    parts = call["json"]["messages"][0]["content"]
    assert parts[1] == {"type": "video_url", "video_url": {"url": VIDEO}}
    assert call["json"]["response_format"]["type"] == "json_schema"
    assert call["json"]["provider"]["only"] == ["google-ai-studio"]
    assert result["url"] == VIDEO
    assert all(key in result for key in REQUIRED_KEYS)


def test_analyze_retries_once_on_schema_mismatch(fake_post, analysis_factory):
    fake_post.queue.append(fake_post.Response(body=fake_post.text_body('{"topic": "only"}')))
    fake_post.queue.append(fake_post.Response(body=fake_post.text_body(_analysis_json(analysis_factory))))

    result = analyze(VIDEO)

    assert len(fake_post.calls) == 2
    assert result["topic"] == analysis_factory()["topic"]


def test_analyze_raises_after_second_mismatch(fake_post):
    fake_post.queue.append(fake_post.Response(body=fake_post.text_body("oops")))
    fake_post.queue.append(fake_post.Response(body=fake_post.text_body('{"topic": "only"}')))

    with pytest.raises(OpenRouterError, match="스키마"):
        analyze(VIDEO)
    assert len(fake_post.calls) == 2


def test_analyze_does_not_retry_http_errors(fake_post):
    fake_post.queue.append(fake_post.Response(status_code=400, text="private video"))

    with pytest.raises(OpenRouterError, match="400"):
        analyze(VIDEO)
    assert len(fake_post.calls) == 1


def test_analyze_rejects_invalid_url_without_calling(fake_post):
    with pytest.raises(OpenRouterError, match="YouTube URL"):
        analyze("https://vimeo.com/1")
    assert fake_post.calls == []
