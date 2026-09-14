"""
Prompt builders and template resolvers for the YouTube pipeline.
Pure functions so format-template behavior is testable without a browser,
an LLM or MoviePy. With template=None every builder returns the legacy prompt.
"""

import re
from typing import Iterable, List, Optional

DEFAULT_SUBTITLE_COLOR = "#FFFF00"
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
MAX_EXISTING_TITLES = 30


def _bullets(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def resolve_language(account_language: str, template: Optional[dict]) -> str:
    if account_language and account_language.strip():
        return account_language
    return (template or {}).get("language") or account_language


def resolve_sentence_count(config_value: int, template: Optional[dict]) -> int:
    count = (template or {}).get("sentence_count")
    if isinstance(count, int) and count > 0:
        return count
    return config_value


def resolve_subtitle_color(template: Optional[dict]) -> str:
    color = str((template or {}).get("subtitle_color") or "")
    return color if HEX_COLOR.match(color) else DEFAULT_SUBTITLE_COLOR


def resolve_tts_style(template: Optional[dict]) -> Optional[str]:
    tone = str((template or {}).get("tone") or "").strip()
    return tone or None


def build_topic_prompt(niche: str, template: Optional[dict], existing_titles: List[str]) -> str:
    if not template:
        return (
            f"Please generate a specific video idea that takes about the following topic: {niche}. "
            "Make it exactly one sentence. Only return the topic, nothing else."
        )

    sections = [
        "Please generate one specific, original YouTube Shorts video idea.",
        f"Channel niche: {template.get('niche') or niche}",
        f"Topic angle: {template.get('topic_angle', '')}",
    ]
    if template.get("example_topics"):
        sections.append(
            "Examples of topics that fit this channel (do not reuse them verbatim):\n"
            + _bullets(template["example_topics"])
        )
    if template.get("avoid"):
        sections.append(
            "Forbidden topics and lines (never reuse or closely paraphrase):\n"
            + _bullets(template["avoid"])
        )
    titles = [title for title in existing_titles if title][-MAX_EXISTING_TITLES:]
    if titles:
        sections.append(
            "Titles this channel already published (do not repeat these topics):\n" + _bullets(titles)
        )
    sections.append("Make it exactly one sentence. Only return the topic, nothing else.")
    return "\n\n".join(sections)


def build_script_prompt(
    subject: str, language: str, sentence_length: int, template: Optional[dict]
) -> str:
    template_directives = ""
    if template:
        lines = [
            f"THE FIRST SENTENCE IS THE HOOK. FOLLOW THIS HOOK PATTERN: {template.get('hook_pattern', '')}",
            f"TONE: {template.get('tone', '')}",
        ]
        if template.get("avoid"):
            lines.append(
                "NEVER REUSE OR CLOSELY PARAPHRASE THESE LINES OR TOPICS:\n" + _bullets(template["avoid"])
            )
        template_directives = "\n".join(lines) + "\n\n"

    return f"""
        Generate a script for a video in {sentence_length} sentences, depending on the subject of the video.

        The script is to be returned as a string with the specified number of paragraphs.

        Here is an example of a string:
        "This is an example string."

        Do not under any circumstance reference this prompt in your response.

        Get straight to the point, don't start with unnecessary things like, "welcome to this video".

        Obviously, the script should be related to the subject of the video.

        YOU MUST NOT EXCEED THE {sentence_length} SENTENCES LIMIT. MAKE SURE THE {sentence_length} SENTENCES ARE SHORT.
        YOU MUST NOT INCLUDE ANY TYPE OF MARKDOWN OR FORMATTING IN THE SCRIPT, NEVER USE A TITLE.
        YOU MUST WRITE THE SCRIPT IN THE LANGUAGE SPECIFIED IN [LANGUAGE].
        ONLY RETURN THE RAW CONTENT OF THE SCRIPT. DO NOT INCLUDE "VOICEOVER", "NARRATOR" OR SIMILAR INDICATORS OF WHAT SHOULD BE SPOKEN AT THE BEGINNING OF EACH PARAGRAPH OR LINE. YOU MUST NOT MENTION THE PROMPT, OR ANYTHING ABOUT THE SCRIPT ITSELF. ALSO, NEVER TALK ABOUT THE AMOUNT OF PARAGRAPHS OR LINES. JUST WRITE THE SCRIPT

{template_directives}        Subject: {subject}
        Language: {language}
        """


def apply_visual_style(image_prompts: list, template: Optional[dict]) -> list:
    style = str((template or {}).get("visual_style") or "").strip()
    if not style:
        return list(image_prompts)
    return [f"{prompt}, {style}" if isinstance(prompt, str) else prompt for prompt in image_prompts]
