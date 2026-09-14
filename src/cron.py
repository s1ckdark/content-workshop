# RUN THIS N AMOUNT OF TIMES
import sys

from status import *
from cache import get_accounts
from config import get_llm_model, get_verbose
from classes.Tts import TTS, unsupported_language_reason
from classes.Twitter import Twitter
from classes.YouTube import YouTube
from llm_provider import select_model
from templates import load_account_template


def get_account_browser_profile(account: dict) -> str:
    """
    Returns the browser profile path with legacy Firefox fallback.

    Args:
        account (dict): Account payload

    Returns:
        path (str): Browser profile path
    """
    return account.get("browser_profile") or account.get("firefox_profile", "")


def main():
    """Main function to post content to Twitter or upload videos to YouTube.

    This function determines its operation based on command-line arguments:
    - If the purpose is "twitter", it initializes a Twitter account and posts a message.
    - If the purpose is "youtube", it initializes a YouTube account, generates a video with TTS, and uploads it.

    Command-line arguments:
        sys.argv[1]: A string indicating the purpose, either "twitter" or "youtube".
        sys.argv[2]: A string representing the account UUID.

    The function also handles verbose output based on user settings and reports success or errors as appropriate.

    Args:
        None. The function uses command-line arguments accessed via sys.argv.

    Returns:
        None. The function performs operations based on the purpose and account UUID and does not return any value."""
    purpose = str(sys.argv[1])
    account_id = str(sys.argv[2])
    model = str(sys.argv[3]) if len(sys.argv) > 3 else get_llm_model()

    if model:
        select_model(model)
    else:
        error("No LLM model specified. Pass model name as third argument or set llm_model in config.json.")
        sys.exit(1)

    verbose = get_verbose()

    if purpose == "twitter":
        accounts = get_accounts("twitter")

        if not account_id:
            error("Account UUID cannot be empty.")

        for acc in accounts:
            if acc["id"] == account_id:
                if verbose:
                    info("Initializing Twitter...")
                twitter = Twitter(
                    acc["id"],
                    acc["nickname"],
                    get_account_browser_profile(acc),
                    acc["topic"]
                )
                twitter.post()
                if verbose:
                    success("Done posting.")
                break
    elif purpose == "youtube":
        tts = TTS()

        accounts = get_accounts("youtube")

        if not account_id:
            error("Account UUID cannot be empty.")

        for acc in accounts:
            if acc["id"] == account_id:
                if verbose:
                    info("Initializing YouTube...")
                template, template_warning = load_account_template(acc)
                if template_warning:
                    warning(template_warning)
                youtube = YouTube(
                    acc["id"],
                    acc["nickname"],
                    get_account_browser_profile(acc),
                    acc["niche"],
                    acc["language"],
                    template=template,
                )
                language_error = unsupported_language_reason(tts.provider, youtube.language)
                if language_error:
                    error(language_error)
                    sys.exit(1)
                youtube.generate_video(tts)
                youtube.upload_video()
                if verbose:
                    success("Uploaded Short.")
                break
    else:
        error("Invalid Purpose, exiting...")
        sys.exit(1)

if __name__ == "__main__":
    main()
