import os
from typing import Any
from urllib.parse import urlparse

from status import *
from config import *
from browser import close_browser_context, get_active_page, launch_persistent_chromium
from constants import *
from llm_provider import generate_text
from .Twitter import Twitter


class AffiliateMarketing:
    """
    Handles affiliate campaign workflows based on product pages and social posting.
    """

    def __init__(
        self,
        affiliate_link: str,
        fp_profile_path: str,
        twitter_account_uuid: str,
        account_nickname: str,
        topic: str,
    ) -> None:
        """
        Initializes the affiliate campaign workflow.

        Args:
            affiliate_link (str): The affiliate link
            fp_profile_path (str): The path to the Chrome user data directory
            twitter_account_uuid (str): The Twitter account UUID
            account_nickname (str): The account nickname
            topic (str): The topic of the product

        Returns:
            None
        """
        self._fp_profile_path: str = fp_profile_path

        self.playwright, self.context = launch_persistent_chromium(fp_profile_path)

        # Set the affiliate link
        self.affiliate_link: str = affiliate_link

        parsed_link = urlparse(self.affiliate_link)
        if parsed_link.scheme not in ["http", "https"] or not parsed_link.netloc:
            raise ValueError(
                f"Affiliate link is invalid. Expected a full URL, got: {self.affiliate_link}"
            )

        # Set the Twitter account UUID
        self.account_uuid: str = twitter_account_uuid

        # Set the Twitter account nickname
        self.account_nickname: str = account_nickname

        # Set the Twitter topic
        self.topic: str = topic

        # Scrape the product information
        self.scrape_product_information()

    def scrape_product_information(self) -> None:
        """
        This method will be used to scrape the product
        information from the affiliate link.
        """
        page = get_active_page(self.context)
        page.goto(self.affiliate_link, wait_until="domcontentloaded")

        # Get the product name
        product_title: str = page.locator(f"#{AMAZON_PRODUCT_TITLE_ID}").inner_text()

        # Get the features of the product
        features: Any = page.locator(f"#{AMAZON_FEATURE_BULLETS_ID} li").all_inner_texts()

        if get_verbose():
            info(f"Product Title: {product_title}")

        if get_verbose():
            info(f"Features: {features}")

        # Set the product title
        self.product_title: str = product_title

        # Set the features
        self.features: Any = features

    def generate_response(self, prompt: str) -> str:
        """
        This method will be used to generate the response for the user.

        Args:
            prompt (str): The prompt for the user.

        Returns:
            response (str): The response for the user.
        """
        return generate_text(prompt)

    def generate_pitch(self) -> str:
        """
        This method will be used to generate a pitch for the product.

        Returns:
            pitch (str): The pitch for the product.
        """
        # Generate the response
        pitch: str = (
            self.generate_response(
                f'I want to promote this product on my website. Generate a brief pitch about this product, return nothing else except the pitch. Information:\nTitle: "{self.product_title}"\nFeatures: "{str(self.features)}"'
            )
            + "\nYou can buy the product here: "
            + self.affiliate_link
        )

        self.pitch: str = pitch

        # Return the response
        return pitch

    def share_pitch(self, where: str) -> None:
        """
        This method will be used to share the pitch on the specified platform.

        Args:
            where (str): The platform where the pitch will be shared.
        """
        if where == "twitter":
            # Initialize the Twitter class
            twitter: Twitter = Twitter(
                self.account_uuid,
                self.account_nickname,
                self._fp_profile_path,
                self.topic,
            )

            # Share the pitch
            try:
                twitter.post(self.pitch)
            finally:
                twitter.close()

    def quit(self) -> None:
        """
        This method will be used to quit the browser.
        """
        # Quit the browser
        close_browser_context(getattr(self, "playwright", None), getattr(self, "context", None))
