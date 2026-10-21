import json

import pytest

from openrouter_client import OpenRouterError
from templates import TemplateCancelled, run_template_pipeline, synthesize

SYNTH = {
    "niche": "생활 속 돈 습관",
    "topic_angle": "일상 속 숨은 손해",
    "hook_pattern": "반대 명령으로 시작",
    "tone": "빠르고 단정적인 반말",
    "visual_style": "bold flat illustration, high contrast",
    "example_topics": ["구독료가 새는 이유", "b", "c", "d", "e"],
}


def test_synthesize_builds_full_template(fake_post, analysis_factory):
    fake_post.queue.append(fake_post.Response(body=fake_post.text_body(json.dumps(SYNTH, ensure_ascii=False))))
    analyses = [
        analysis_factory(url="https://www.youtube.com/watch?v=AAAAAAAAAAA", sentence_count=5),
        analysis_factory(
            url="https://www.youtube.com/watch?v=BBBBBBBBBBB",
            topic="Rent vs buy",
            hook_text="You are losing money.",
            sentence_count=7,
        ),
    ]

    template = synthesize(analyses, "돈 습관")

    assert template["name"] == "돈 습관"
    assert template["id"]
    assert template["created_at"]
    assert template["source_urls"] == [a["url"] for a in analyses]
    assert template["niche"] == "생활 속 돈 습관"
    assert template["example_topics"][0] == "구독료가 새는 이유"
    assert template["sentence_count"] == 6
    assert template["subtitle_color"] == "#FFFFFF"
    assert template["language"] == "korean"
    assert "Rent vs buy" in template["avoid"]
    assert template["analyses"] == analyses

    sent_prompt = fake_post.calls[0]["json"]["messages"][0]["content"]
    assert "Rent vs buy" in sent_prompt
    assert fake_post.calls[0]["url"].endswith("/chat/completions")


def test_synthesize_retries_once_then_succeeds(fake_post, analysis_factory):
    fake_post.queue.append(fake_post.Response(body=fake_post.text_body("oops")))
    fake_post.queue.append(fake_post.Response(body=fake_post.text_body(json.dumps(SYNTH))))

    template = synthesize([analysis_factory()], "x")

    assert len(fake_post.calls) == 2
    assert template["tone"] == SYNTH["tone"]


def test_synthesize_retries_http_error_then_raises(fake_post, analysis_factory):
    fake_post.queue.append(fake_post.Response(status_code=500, text="err"))
    fake_post.queue.append(fake_post.Response(body=fake_post.text_body('{"niche": "only"}')))

    with pytest.raises(OpenRouterError):
        synthesize([analysis_factory()], "x")
    assert len(fake_post.calls) == 2


def test_synthesize_requires_analyses():
    with pytest.raises(ValueError):
        synthesize([], "x")


def _pipeline(urls, analyze_fn, cancelled=lambda: False, on_failure=None):
    progress = []
    result = run_template_pipeline(
        urls,
        "name",
        analyze_fn=analyze_fn,
        synthesize_fn=lambda analyses, name: {"name": name, "count": len(analyses)},
        on_progress=lambda label, pct: progress.append((label, pct)),
        is_cancelled=cancelled,
        on_failure=on_failure,
    )
    return result, progress


def test_pipeline_skips_failed_urls():
    def analyze_fn(url):
        if url == "bad":
            raise OpenRouterError("private video")
        return {"url": url}

    (template, failures), progress = _pipeline(["good1", "bad", "good2"], analyze_fn)

    assert template == {"name": "name", "count": 2}
    assert len(failures) == 1 and "bad" in failures[0] and "private video" in failures[0]
    assert progress[-1] == ("템플릿 합성 중", 85)
    assert [p for _, p in progress] == sorted(p for _, p in progress)


def test_pipeline_calls_on_failure_immediately_per_url():
    def analyze_fn(url):
        if url == "bad":
            raise OpenRouterError("private video")
        return {"url": url}

    reported = []
    (template, failures), _progress = _pipeline(
        ["good1", "bad", "good2"], analyze_fn, on_failure=reported.append
    )

    assert template == {"name": "name", "count": 2}
    assert reported == failures
    assert len(reported) == 1 and "bad" in reported[0] and "private video" in reported[0]


def test_pipeline_raises_when_all_fail():
    def analyze_fn(url):
        raise OpenRouterError("nope")

    with pytest.raises(RuntimeError, match="모든 레퍼런스"):
        _pipeline(["a", "b"], analyze_fn)


def test_pipeline_honors_cancel():
    with pytest.raises(TemplateCancelled):
        _pipeline(["a"], lambda url: {"url": url}, cancelled=lambda: True)
