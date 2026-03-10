import re
import sys
import time
import os
import json

from cache import *
from config import *
from status import *
from browser import close_browser_context, get_active_page, launch_persistent_chromium
from llm_provider import generate_text
from typing import List, Optional
from datetime import datetime
from termcolor import colored


class Twitter:
    """
    Automates content generation and posting for a Twitter/X account.
    """

    def __init__(
        self, account_uuid: str, account_nickname: str, fp_profile_path: str, topic: str
    ) -> None:
        """
        Initializes the Twitter/X automation client.

        Args:
            account_uuid (str): The account UUID
            account_nickname (str): The account nickname
            fp_profile_path (str): The path to the Chrome user data directory

        Returns:
            None
        """
        self.account_uuid: str = account_uuid
        self.account_nickname: str = account_nickname
        self.fp_profile_path: str = fp_profile_path
        self.topic: str = topic

        self.playwright, self.context = launch_persistent_chromium(fp_profile_path)

    def post(self, text: Optional[str] = None) -> None:
        """
        Publishes content to Twitter/X.

        Args:
            text (str): The text to post

        Returns:
            None
        """
        verbose: bool = get_verbose()
        page = get_active_page(self.context)

        page.goto("https://x.com/compose/post", wait_until="domcontentloaded")

        post_content: str = text if text is not None else self.generate_post()
        now: datetime = datetime.now()

        print(colored(" => Posting to Twitter:", "blue"), post_content[:30] + "...")
        body = post_content

        text_box = None
        text_box_selectors = [
            "css=div[data-testid='tweetTextarea_0'][role='textbox']",
            "xpath=//div[@data-testid='tweetTextarea_0']//div[@role='textbox']",
            "xpath=//div[@role='textbox']",
        ]

        for selector in text_box_selectors:
            try:
                candidate = page.locator(selector).first
                candidate.wait_for(state="visible")
                candidate.click()
                page.keyboard.type(body)
                text_box = candidate
                break
            except Exception:
                continue

        if text_box is None:
            raise RuntimeError(
                "Could not find tweet text box. Ensure you are logged into X in this Chrome profile."
            )


        post_button = None
        post_button_selectors = [
            "xpath=//button[@data-testid='tweetButtonInline']",
            "xpath=//button[@data-testid='tweetButton']",
            "xpath=//span[text()='Post']/ancestor::button",
        ]

        for selector in post_button_selectors:
            try:
                candidate = page.locator(selector).first
                candidate.wait_for(state="visible")
                candidate.click()
                post_button = candidate
                break
            except Exception:
                continue

        if post_button is None:
            raise RuntimeError("Could not find the Post button on X compose screen.")

        if verbose:
            print(colored(" => Pressed [ENTER] Button on Twitter..", "blue"))
        time.sleep(2)

        # Add the post to the cache
        self.add_post({"content": body, "date": now.strftime("%m/%d/%Y, %H:%M:%S")})

        success("Posted to Twitter successfully!")

    def get_posts(self) -> List[dict]:
        """
        Gets the posts from the cache.

        Returns:
            posts (List[dict]): The posts
        """
        if not os.path.exists(get_twitter_cache_path()):
            write_json_atomic(get_twitter_cache_path(), {"accounts": []})

        with open(get_twitter_cache_path(), "r") as file:
            parsed = json.load(file)

            # Find our account
            accounts = parsed["accounts"]
            for account in accounts:
                if account["id"] == self.account_uuid:
                    posts = account["posts"]

                    if posts is None:
                        return []

                    # Return the posts
                    return posts

        return []

    def add_post(self, post: dict) -> None:
        """
        Adds a post to the cache.

        Args:
            post (dict): The post to add

        Returns:
            None
        """
        with open(get_twitter_cache_path(), "r") as file:
            previous_json = json.loads(file.read())

            # Find our account
            accounts = previous_json["accounts"]
            for account in accounts:
                if account["id"] == self.account_uuid:
                    account["posts"].append(post)

            write_json_atomic(get_twitter_cache_path(), previous_json)

    def generate_post(self) -> str:
        """
        Generates a post for the Twitter account based on the topic.

        Returns:
            post (str): The post
        """
        completion = generate_text(
            f"Generate a Twitter post about: {self.topic} in {get_twitter_language()}. "
            "The Limit is 2 sentences. Choose a specific sub-topic of the provided topic."
        )

        if get_verbose():
            info("Generating a post...")

        if completion is None:
            error("Failed to generate a post. Please try again.")
            sys.exit(1)

        # Apply Regex to remove all *
        completion = re.sub(r"\*", "", completion).replace('"', "")

        if get_verbose():
            info(f"Length of post: {len(completion)}")
        if len(completion) >= 260:
            return completion[:257].rsplit(" ", 1)[0] + "..."

        return completion

    def close(self) -> None:
        """
        Closes the browser session safely.

        Returns:
            None
        """
        close_browser_context(getattr(self, "playwright", None), getattr(self, "context", None))
