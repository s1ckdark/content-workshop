import re
import json
import time
import os

from utils import *
from cache import *
from .Tts import TTS
from openrouter_client import OpenRouterError
from openrouter_media import generate_image as generate_openrouter_image, transcribe_subtitles
from browser import close_browser_context, get_active_page, launch_persistent_chromium
from llm_provider import generate_text
from config import *
from status import *
from uuid import uuid4
from constants import *
from typing import List, Optional
from termcolor import colored
from moviepy.video.tools.subtitles import SubtitlesClip
from datetime import datetime

try:
    from moviepy.config import change_settings
except ImportError:
    change_settings = None

try:
    from moviepy import (
        AudioFileClip,
        CompositeAudioClip,
        CompositeVideoClip,
        ImageClip,
        TextClip,
        afx,
        concatenate_videoclips,
        vfx,
    )
    _HAS_MOVIEPY_V2 = True
except ImportError:
    from moviepy.editor import (
        AudioFileClip,
        CompositeAudioClip,
        CompositeVideoClip,
        ImageClip,
        TextClip,
        afx,
        concatenate_videoclips,
    )
    from moviepy.video.fx.all import crop

    vfx = None
    _HAS_MOVIEPY_V2 = False

# Set ImageMagick Path when the installed MoviePy version supports it.
if change_settings is not None:
    change_settings({"IMAGEMAGICK_BINARY": get_imagemagick_path()})


def _with_fps(clip, fps):
    return clip.with_fps(fps) if hasattr(clip, "with_fps") else clip.set_fps(fps)


def _with_duration(clip, duration):
    return (
        clip.with_duration(duration)
        if hasattr(clip, "with_duration")
        else clip.set_duration(duration)
    )


def _with_audio(clip, audio):
    return clip.with_audio(audio) if hasattr(clip, "with_audio") else clip.set_audio(audio)


def _with_position(clip, position):
    return (
        clip.with_position(position)
        if hasattr(clip, "with_position")
        else clip.set_pos(position)
    )


def _with_start(clip, start_time):
    return (
        clip.with_start(start_time)
        if hasattr(clip, "with_start")
        else clip.set_start(start_time)
    )


def _with_fadeout(clip, duration):
    if vfx is not None and hasattr(vfx, "FadeOut") and hasattr(clip, "with_effects"):
        return clip.with_effects([vfx.FadeOut(duration)])
    if hasattr(clip, "fadeout"):
        return clip.fadeout(duration)
    return clip


def _resize_clip(clip, size):
    return clip.resized(new_size=size) if hasattr(clip, "resized") else clip.resize(size)


def _with_volume_scaled(clip, factor):
    if hasattr(clip, "with_volume_scaled"):
        return clip.with_volume_scaled(factor)

    return clip.fx(afx.volumex, factor)


def _crop_clip(clip, **kwargs):
    if vfx is not None and hasattr(clip, "with_effects"):
        return clip.with_effects([vfx.Crop(**kwargs)])

    return crop(clip, **kwargs)


def _resolve_font_path(text: str = "") -> str:
    """Returns the best available font path, falling back to AppleGothic on macOS for Korean characters."""
    default_font = os.path.join(get_fonts_dir(), get_font())
    has_korean = any("\uac00" <= ch <= "\ud7a3" for ch in (text or ""))
    if has_korean:
        candidates = [
            "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
    return default_font if os.path.exists(default_font) else get_font()


class YouTube:
    """
    Class for YouTube Automation.

    Steps to create a YouTube Short:
    1. Generate a topic [DONE]
    2. Generate a script [DONE]
    3. Generate metadata (Title, Description, Tags) [DONE]
    4. Generate AI Image Prompts [DONE]
    4. Generate Images based on generated Prompts [DONE]
    5. Convert Text-to-Speech [DONE]
    6. Show images each for n seconds, n: Duration of TTS / Amount of images [DONE]
    7. Combine Concatenated Images with the Text-to-Speech [DONE]
    """

    def __init__(
        self,
        account_uuid: str,
        account_nickname: str,
        fp_profile_path: str,
        niche: str,
        language: str,
    ) -> None:
        """
        Constructor for YouTube Class.

        Args:
            account_uuid (str): The unique identifier for the YouTube account.
            account_nickname (str): The nickname for the YouTube account.
            fp_profile_path (str): Path to the Chrome user data dir logged into the specified YouTube account.
            niche (str): The niche of the provided YouTube Channel.
            language (str): The language of the Automation.

        Returns:
            None
        """
        self._account_uuid: str = account_uuid
        self._account_nickname: str = account_nickname
        self._fp_profile_path: str = fp_profile_path
        self._niche: str = niche
        self._language: str = language

        self.images = []
        self.title_image_path: Optional[str] = None
        self.thumbnail_path: Optional[str] = None
        self.playwright, self.context = launch_persistent_chromium(self._fp_profile_path)

    @property
    def niche(self) -> str:
        """
        Getter Method for the niche.

        Returns:
            niche (str): The niche
        """
        return self._niche

    @property
    def language(self) -> str:
        """
        Getter Method for the language to use.

        Returns:
            language (str): The language
        """
        return self._language

    def generate_response(self, prompt: str, model_name: str = None) -> str:
        """
        Generates an LLM Response based on a prompt and the user-provided model.

        Args:
            prompt (str): The prompt to use in the text generation.

        Returns:
            response (str): The generated AI Repsonse.
        """
        return generate_text(prompt, model_name=model_name)

    def generate_topic(self) -> str:
        """
        Generates a topic based on the YouTube Channel niche.

        Returns:
            topic (str): The generated topic.
        """
        completion = self.generate_response(
            f"Please generate a specific video idea that takes about the following topic: {self.niche}. Make it exactly one sentence. Only return the topic, nothing else."
        )

        if not completion:
            error("Failed to generate Topic.")

        self.subject = completion

        return completion

    def generate_script(self) -> str:
        """
        Generate a script for a video, depending on the subject of the video, the number of paragraphs, and the AI model.

        Returns:
            script (str): The script of the video.
        """
        sentence_length = get_script_sentence_length()
        prompt = f"""
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
        
        Subject: {self.subject}
        Language: {self.language}
        """
        completion = self.generate_response(prompt)

        # Apply regex to remove *
        completion = re.sub(r"\*", "", completion)

        if not completion:
            error("The generated script is empty.")
            return

        if len(completion) > 5000:
            if get_verbose():
                warning("Generated Script is too long. Retrying...")
            return self.generate_script()

        self.script = completion

        return completion

    def generate_metadata(self) -> dict:
        """
        Generates Video metadata for the to-be-uploaded YouTube Short (Title, Description).

        Returns:
            metadata (dict): The generated metadata.
        """
        title = self.generate_response(
            f"Please generate a YouTube Video Title for the following subject, including hashtags: {self.subject}. Only return the title, nothing else. Limit the title under 100 characters."
        )

        if len(title) > 100:
            if get_verbose():
                warning("Generated Title is too long. Retrying...")
            return self.generate_metadata()

        description = self.generate_response(
            f"Please generate a YouTube Video Description for the following script: {self.script}. Only return the description, nothing else."
        )

        self.metadata = {"title": title, "description": description}

        return self.metadata

    def generate_prompts(self) -> List[str]:
        """
        Generates AI Image Prompts based on the provided Video Script.
        The first prompt is specifically crafted as an eye-catching Title/Cover image.

        Returns:
            image_prompts (List[str]): Generated List of image prompts.
        """
        n_prompts = max(int(len(self.script) / 3), 2)
        video_title = (
            self.metadata.get("title", "")
            if hasattr(self, "metadata") and isinstance(self.metadata, dict)
            else ""
        )

        prompt = f"""
        Generate {n_prompts} Image Prompts for AI Image Generation,
        depending on the subject and script of a video.
        Subject: {self.subject}
        Title: {video_title}

        CRITICAL REQUIREMENTS:
        - The FIRST prompt (index 0) MUST be an eye-catching, highly dramatic Title / Cover image prompt
          that visually represents the video title ('{video_title}'). It should serve as a high-impact opening hook for YouTube Shorts.
        - The subsequent prompts (index 1 to {n_prompts - 1}) must visualize the progression of scenes in the script.

        The image prompts are to be returned as
        a JSON-Array of strings.

        Each search term should consist of a full sentence,
        always add the main subject of the video.

        Be emotional and use interesting adjectives to make the
        Image Prompt as detailed as possible.

        YOU MUST ONLY RETURN THE JSON-ARRAY OF STRINGS.
        YOU MUST NOT RETURN ANYTHING ELSE.
        YOU MUST NOT RETURN THE SCRIPT.

        The search terms must be related to the subject of the video.
        Here is an example of a JSON-Array of strings:
        ["Eye-catching title cover image for {video_title}...", "scene 2 prompt...", "scene 3 prompt..."]

        For context, here is the full text:
        {self.script}
        """

        completion = (
            str(self.generate_response(prompt))
            .replace("```json", "")
            .replace("```", "")
        )

        image_prompts = []

        if "image_prompts" in completion:
            image_prompts = json.loads(completion)["image_prompts"]
        else:
            try:
                image_prompts = json.loads(completion)
                if get_verbose():
                    info(f" => Generated Image Prompts: {image_prompts}")
            except Exception:
                if get_verbose():
                    warning(
                        "LLM returned an unformatted response. Attempting to clean..."
                    )

                # Get everything between [ and ], and turn it into a list
                r = re.compile(r"\[.*\]")
                image_prompts = r.findall(completion)
                if len(image_prompts) == 0:
                    if get_verbose():
                        warning("Failed to generate Image Prompts. Retrying...")
                    return self.generate_prompts()

        if len(image_prompts) > n_prompts:
            image_prompts = image_prompts[: int(n_prompts)]

        self.image_prompts = image_prompts

        success(f"Generated {len(image_prompts)} Image Prompts (including Title image).")

        return image_prompts

    def _persist_image(self, image_bytes: bytes, provider_label: str) -> str:
        """
        Writes generated image bytes to a PNG file in .mp.

        Args:
            image_bytes (bytes): Image payload
            provider_label (str): Label for logging

        Returns:
            path (str): Absolute image path
        """
        image_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".png")

        with open(image_path, "wb") as image_file:
            image_file.write(image_bytes)

        if get_verbose():
            info(f' => Wrote image from {provider_label} to "{image_path}"')

        self.images.append(image_path)

        if self.title_image_path is None:
            self.title_image_path = image_path
            # Also save as dedicated thumbnail file
            thumbnail_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + "_thumbnail.png")
            try:
                with open(thumbnail_path, "wb") as thumb_file:
                    thumb_file.write(image_bytes)
                self.thumbnail_path = thumbnail_path
                if hasattr(self, "metadata") and isinstance(self.metadata, dict):
                    self.metadata["thumbnail_path"] = thumbnail_path
                if get_verbose():
                    info(f' => Saved title thumbnail to "{thumbnail_path}"')
            except Exception as e:
                warning(f"Failed to create thumbnail copy: {e}")

        return image_path

    def generate_image(self, prompt: str) -> str:
        """Generates and saves a PNG using OpenRouter's image API."""
        try:
            return self._persist_image(generate_openrouter_image(prompt), "OpenRouter")
        except OpenRouterError as exc:
            warning(f"이미지 생성 실패: {exc}")
            return None

    def generate_image_nanobanana2(self, prompt: str) -> str:
        """Compatibility alias; all image requests now use OpenRouter."""
        return self.generate_image(prompt)

    def generate_title_image(self, title: Optional[str] = None) -> Optional[str]:
        """
        Generates a dedicated title/cover image for the video based on its title and subject.

        Args:
            title (Optional[str]): Video title. Defaults to metadata['title'] or subject.

        Returns:
            image_path (Optional[str]): Path to the generated title image.
        """
        target_title = (
            title
            or (self.metadata.get("title") if hasattr(self, "metadata") and isinstance(self.metadata, dict) else None)
            or getattr(self, "subject", "Interesting story")
        )
        prompt = (
            f"Eye-catching, dramatic, high-impact Title and Cover image for a viral video titled: '{target_title}'. "
            f"Subject: {getattr(self, 'subject', target_title)}. "
            f"Vibrant colors, cinematic composition, captivating visual hook, 8k resolution concept art, YouTube Shorts cover."
        )
        if get_verbose():
            info(f"Generating dedicated Title Image with prompt: {prompt}")
        image_path = self.generate_image(prompt)
        if image_path:
            self.title_image_path = image_path
            success(f"Generated title image: {image_path}")
        return image_path

    def generate_script_to_speech(self, tts_instance: TTS) -> str:
        """
        Converts the generated script into Speech using the configured TTS provider and returns the path to the wav file.

        Args:
            tts_instance (tts): Instance of TTS Class.

        Returns:
            path_to_wav (str): Path to generated audio (WAV Format).
        """
        path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".wav")

        # Clean script, remove every character that is not a word character, a space, a period, a question mark, or an exclamation mark.
        self.script = re.sub(r"[^\w\s.?!]", "", self.script)

        tts_instance.synthesize(self.script, path)

        self.tts_path = path

        if get_verbose():
            info(f' => Wrote TTS to "{path}"')

        return path

    def add_video(self, video: dict) -> None:
        """
        Adds a video to the cache.

        Args:
            video (dict): The video to add

        Returns:
            None
        """
        cache = get_youtube_cache_path()

        with open(cache, "r") as file:
            previous_json = json.loads(file.read())

            # Find our account
            accounts = previous_json["accounts"]
            for account in accounts:
                if account["id"] == self._account_uuid:
                    account["videos"].append(video)

            write_json_atomic(cache, previous_json)

    def generate_subtitles(self, audio_path: str) -> str:
        """Generates timed SRT captions through the selected STT provider."""
        provider = str(get_stt_provider()).strip().lower()
        if provider == "openrouter":
            srt_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".srt")
            return transcribe_subtitles(audio_path, srt_path, self._language)
        if provider == "local_whisper":
            return self.generate_subtitles_local_whisper(audio_path)
        raise ValueError(f"지원하지 않는 stt_provider입니다: {provider}")

    def _format_srt_timestamp(self, seconds: float) -> str:
        """
        Formats a timestamp in seconds to SRT format.

        Args:
            seconds (float): Seconds

        Returns:
            ts (str): HH:MM:SS,mmm
        """
        total_millis = max(0, int(round(seconds * 1000)))
        hours = total_millis // 3600000
        minutes = (total_millis % 3600000) // 60000
        secs = (total_millis % 60000) // 1000
        millis = total_millis % 1000
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def generate_subtitles_local_whisper(self, audio_path: str) -> str:
        """
        Generates subtitles using local Whisper (faster-whisper).

        Args:
            audio_path (str): Audio file path

        Returns:
            path (str): Path to SRT file
        """
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            error(
                "Local STT selected but 'faster-whisper' is not installed. "
                "Install it or switch stt_provider to openrouter."
            )
            raise

        model = WhisperModel(
            get_whisper_model(),
            device=get_whisper_device(),
            compute_type=get_whisper_compute_type(),
        )
        segments, _ = model.transcribe(audio_path, vad_filter=True)

        lines = []
        for idx, segment in enumerate(segments, start=1):
            start = self._format_srt_timestamp(segment.start)
            end = self._format_srt_timestamp(segment.end)
            text = str(segment.text).strip()

            if not text:
                continue

            lines.append(str(idx))
            lines.append(f"{start} --> {end}")
            lines.append(text)
            lines.append("")

        subtitles = "\n".join(lines)
        srt_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".srt")
        with open(srt_path, "w", encoding="utf-8") as file:
            file.write(subtitles)

        return srt_path

    def combine(self) -> str:
        """
        Combines everything into the final video.

        Returns:
            path (str): The path to the generated MP4 File.
        """
        combined_image_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".mp4")
        threads = get_threads()
        tts_clip = AudioFileClip(self.tts_path)
        max_duration = tts_clip.duration
        req_dur = max_duration / len(self.images)

        # Make a generator that returns a TextClip when called with consecutive
        def generator(txt):
            clip_kwargs = {
                "font": _resolve_font_path(txt),
                "color": "#FFFF00",
                "stroke_color": "black",
                "stroke_width": 5,
                "size": (1080, 1920),
                "method": "caption",
            }

            if _HAS_MOVIEPY_V2:
                clip_kwargs["text"] = txt
                clip_kwargs["font_size"] = 100
            else:
                clip_kwargs["txt"] = txt
                clip_kwargs["fontsize"] = 100

            return TextClip(**clip_kwargs)

        print(colored("[+] Combining images...", "blue"))

        clips = []
        tot_dur = 0
        # Add downloaded clips over and over until the duration of the audio (max_duration) has been reached
        while tot_dur < max_duration:
            for image_path in self.images:
                clip = ImageClip(image_path)
                clip = _with_duration(clip, req_dur)
                clip = _with_fps(clip, 30)

                # Not all images are same size,
                # so we need to resize them
                if round((clip.w / clip.h), 4) < 0.5625:
                    if get_verbose():
                        info(f" => Resizing Image: {image_path} to 1080x1920")
                    clip = _crop_clip(
                        clip,
                        width=clip.w,
                        height=round(clip.w / 0.5625),
                        x_center=clip.w / 2,
                        y_center=clip.h / 2,
                    )
                else:
                    if get_verbose():
                        info(f" => Resizing Image: {image_path} to 1920x1080")
                    clip = _crop_clip(
                        clip,
                        width=round(0.5625 * clip.h),
                        height=clip.h,
                        x_center=clip.w / 2,
                        y_center=clip.h / 2,
                    )
                clip = _resize_clip(clip, (1080, 1920))

                # FX (Fade In)
                # clip = clip.fadein(2)

                clips.append(clip)
                tot_dur += clip.duration

        final_clip = concatenate_videoclips(clips)
        final_clip = _with_fps(final_clip, 30)
        random_song = choose_random_song()

        # Title Card Overlay (Shown during the intro / first scene)
        title_clip = None
        video_title = (
            self.metadata.get("title", "")
            if hasattr(self, "metadata") and isinstance(self.metadata, dict)
            else ""
        )
        if video_title:
            try:
                title_font = _resolve_font_path(video_title)
                title_dur = min(max(req_dur, 2.5), 4.0)
                t_kwargs = {
                    "font": title_font,
                    "color": "#FFFFFF",
                    "stroke_color": "black",
                    "stroke_width": 6,
                    "size": (960, None),
                    "method": "caption",
                }
                if _HAS_MOVIEPY_V2:
                    t_kwargs["text"] = video_title
                    t_kwargs["font_size"] = 72
                else:
                    t_kwargs["txt"] = video_title
                    t_kwargs["fontsize"] = 72

                raw_title_clip = TextClip(**t_kwargs)
                raw_title_clip = _with_duration(raw_title_clip, title_dur)
                raw_title_clip = _with_position(raw_title_clip, ("center", 350))
                title_clip = _with_fadeout(raw_title_clip, 0.6)
                if get_verbose():
                    info(f" => Added Title Card overlay: '{video_title}' ({title_dur:.1f}s)")
            except Exception as e:
                warning(f"Failed to create Title Card overlay: {e}")

        subtitles = None
        try:
            subtitles_path = self.generate_subtitles(self.tts_path)
            equalize_subtitles(subtitles_path, 10)
            subtitles = SubtitlesClip(subtitles_path, make_textclip=generator, encoding="utf-8")
            subtitles = _with_position(subtitles, ("center", "center"))
        except Exception as e:
            warning(f"Failed to generate subtitles, continuing without subtitles: {e}")

        random_song_clip = _with_fps(AudioFileClip(random_song), 44100)

        # Turn down volume
        random_song_clip = _with_volume_scaled(random_song_clip, 0.1)
        comp_audio = CompositeAudioClip([_with_fps(tts_clip, 44100), random_song_clip])

        final_clip = _with_audio(final_clip, comp_audio)
        final_clip = _with_duration(final_clip, tts_clip.duration)

        video_layers = [final_clip]
        if title_clip is not None:
            video_layers.append(title_clip)
        if subtitles is not None:
            video_layers.append(subtitles)

        if len(video_layers) > 1:
            final_clip = CompositeVideoClip(video_layers)

        final_clip.write_videofile(combined_image_path, threads=threads)

        success(f'Wrote Video to "{combined_image_path}"')

        return combined_image_path

    def generate_video(self, tts_instance: TTS) -> str:
        """
        Generates a YouTube Short based on the provided niche and language.

        Args:
            tts_instance (TTS): Instance of TTS Class.

        Returns:
            path (str): The path to the generated MP4 File.
        """
        # Generate the Topic
        self.generate_topic()

        # Generate the Script
        self.generate_script()

        # Generate the Metadata
        self.generate_metadata()

        # Generate the Image Prompts
        self.generate_prompts()

        # Generate the Images
        for prompt in self.image_prompts:
            self.generate_image(prompt)

        if len(self.images) == 0:
            raise RuntimeError(
                "No images were generated. Check your OpenRouter configuration."
            )

        # Generate the TTS
        self.generate_script_to_speech(tts_instance)

        # Combine everything
        path = self.combine()

        if get_verbose():
            info(f" => Generated Video: {path}")

        self.video_path = os.path.abspath(path)

        return path

    def get_channel_id(self) -> str:
        """
        Gets the Channel ID of the YouTube Account.

        Returns:
            channel_id (str): The Channel ID.
        """
        page = get_active_page(self.context)
        page.goto("https://studio.youtube.com", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        channel_id = page.url.rstrip("/").split("/")[-1].split("?")[0]
        self.channel_id = channel_id

        return channel_id

    def upload_video(self) -> bool:
        """
        Uploads the video to YouTube.

        Returns:
            success (bool): Whether the upload was successful or not.
        """
        try:
            self.get_channel_id()

            page = get_active_page(self.context)
            verbose = get_verbose()

            # Go to youtube.com/upload
            page.goto("https://www.youtube.com/upload", wait_until="domcontentloaded")

            # Set video file
            page.locator("ytcp-uploads-file-picker input[type='file']").set_input_files(
                self.video_path
            )

            # Wait for upload to finish
            page.wait_for_timeout(5000)

            # Set title
            title_el = page.locator(f"#{YOUTUBE_TEXTBOX_ID}").first
            description_el = page.locator(f"#{YOUTUBE_TEXTBOX_ID}").last

            if verbose:
                info("\t=> Setting title...")

            title_el.click()
            page.keyboard.press("ControlOrMeta+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(self.metadata["title"])

            if verbose:
                info("\t=> Setting description...")

            # Set description
            page.wait_for_timeout(10000)
            description_el.click()
            page.keyboard.press("ControlOrMeta+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(self.metadata["description"])

            page.wait_for_timeout(500)

            # Set `made for kids` option
            if verbose:
                info("\t=> Setting `made for kids` option...")

            is_for_kids_checkbox = page.locator(
                f"[name='{YOUTUBE_MADE_FOR_KIDS_NAME}']"
            ).first
            is_not_for_kids_checkbox = page.locator(
                f"[name='{YOUTUBE_NOT_MADE_FOR_KIDS_NAME}']"
            ).first

            if not get_is_for_kids():
                is_not_for_kids_checkbox.click()
            else:
                is_for_kids_checkbox.click()

            page.wait_for_timeout(500)

            # Click next
            if verbose:
                info("\t=> Clicking next...")

            next_button = page.locator(f"#{YOUTUBE_NEXT_BUTTON_ID}").first
            next_button.click()

            # Click next again
            if verbose:
                info("\t=> Clicking next again...")
            next_button = page.locator(f"#{YOUTUBE_NEXT_BUTTON_ID}").first
            next_button.click()

            # Wait for 2 seconds
            page.wait_for_timeout(2000)

            # Click next again
            if verbose:
                info("\t=> Clicking next again...")
            next_button = page.locator(f"#{YOUTUBE_NEXT_BUTTON_ID}").first
            next_button.click()

            # Set as unlisted
            if verbose:
                info("\t=> Setting as unlisted...")

            page.locator(f"xpath={YOUTUBE_RADIO_BUTTON_XPATH}").nth(2).click()

            if verbose:
                info("\t=> Clicking done button...")

            # Click done button
            done_button = page.locator(f"#{YOUTUBE_DONE_BUTTON_ID}").first
            done_button.click()

            # Wait for 2 seconds
            page.wait_for_timeout(2000)

            # Get latest video
            if verbose:
                info("\t=> Getting video URL...")

            # Get the latest uploaded video URL
            page.goto(
                f"https://studio.youtube.com/channel/{self.channel_id}/videos/short",
                wait_until="domcontentloaded",
            )
            page.wait_for_timeout(2000)
            href = (
                page.locator("ytcp-video-row")
                .first
                .locator("a")
                .first
                .get_attribute("href")
            )
            if not href:
                raise RuntimeError("Could not resolve uploaded video URL from YouTube Studio.")
            if verbose:
                info(f"\t=> Extracting video ID from URL: {href}")
            video_id = href.split("/")[-2]

            # Build URL
            url = build_url(video_id)

            self.uploaded_video_url = url

            if verbose:
                success(f" => Uploaded Video: {url}")

            # Add video to cache
            self.add_video(
                {
                    "title": self.metadata["title"],
                    "description": self.metadata["description"],
                    "url": url,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

            return True
        except Exception as exc:
            error(f"Failed to upload video: {exc}")
            return False

    def get_videos(self) -> List[dict]:
        """
        Gets the uploaded videos from the YouTube Channel.

        Returns:
            videos (List[dict]): The uploaded videos.
        """
        if not os.path.exists(get_youtube_cache_path()):
            # Create the cache file
            write_json_atomic(get_youtube_cache_path(), {"accounts": []})
            return []

        videos = []
        # Read the cache file
        with open(get_youtube_cache_path(), "r") as file:
            previous_json = json.loads(file.read())
            # Find our account
            accounts = previous_json.get("accounts", [])
            for account in accounts:
                if account["id"] == self._account_uuid:
                    videos = account["videos"]

        return videos

    def close(self) -> None:
        """
        Closes the browser session safely.

        Returns:
            None
        """
        close_browser_context(getattr(self, "playwright", None), getattr(self, "context", None))
