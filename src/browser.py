import os

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

from config import get_headless


def launch_persistent_chromium(user_data_dir: str) -> tuple[Playwright, BrowserContext]:
    """
    Launches a persistent Chromium context backed by a local Chrome profile dir.

    Args:
        user_data_dir (str): Chrome/Chromium user data directory

    Returns:
        tuple[Playwright, BrowserContext]: Active Playwright handle and context
    """
    if not os.path.isdir(user_data_dir):
        raise ValueError(
            f"Browser profile path does not exist or is not a directory: {user_data_dir}"
        )

    playwright = sync_playwright().start()

    launch_kwargs = {
        "user_data_dir": user_data_dir,
        "headless": get_headless(),
    }

    try:
        context = playwright.chromium.launch_persistent_context(
            channel="chrome", **launch_kwargs
        )
    except Exception:
        context = playwright.chromium.launch_persistent_context(**launch_kwargs)

    context.set_default_timeout(30000)
    return playwright, context


def get_active_page(context: BrowserContext) -> Page:
    """
    Returns an existing page when available, otherwise creates one.

    Args:
        context (BrowserContext): Active browser context

    Returns:
        Page: Page to interact with
    """
    return context.pages[0] if context.pages else context.new_page()


def close_browser_context(
    playwright: Playwright | None, context: BrowserContext | None
) -> None:
    """
    Closes browser context and Playwright safely.

    Args:
        playwright (Playwright | None): Playwright handle
        context (BrowserContext | None): Browser context

    Returns:
        None
    """
    try:
        if context is not None:
            context.close()
    except Exception:
        pass

    try:
        if playwright is not None:
            playwright.stop()
    except Exception:
        pass
