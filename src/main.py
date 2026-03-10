import os
import schedule
import subprocess
import sys
import time

from art import *
from cache import *
from utils import *
from config import *
from status import *
from uuid import uuid4
from constants import *
from classes.Tts import TTS
from termcolor import colored
from classes.Twitter import Twitter
from classes.YouTube import YouTube
from prettytable import PrettyTable
from classes.Outreach import Outreach
from classes.AFM import AffiliateMarketing
from llm_provider import list_models, select_model, get_active_model


def ensure_model_selected() -> str | None:
    """
    Ensures an Ollama model is selected before LLM-backed workflows run.

    Returns:
        model (str | None): Selected model, or None when selection failed.
    """
    active_model = get_active_model()
    if active_model:
        return active_model

    configured_model = get_ollama_model()
    if configured_model:
        select_model(configured_model)
        success(f"Using configured model: {configured_model}")
        return configured_model

    try:
        models = list_models()
    except Exception as e:
        error(f"Could not connect to Ollama: {e}")
        return None

    if not models:
        error("No models found on Ollama. Pull a model first (e.g. 'ollama pull llama3.2:3b').")
        return None

    info("\n========== OLLAMA MODELS =========", False)
    for idx, model_name in enumerate(models):
        print(colored(f" {idx + 1}. {model_name}", "cyan"))
    info("==================================\n", False)

    selected_model = None
    while selected_model is None:
        raw = input(colored("Select a model: ", "magenta")).strip()
        try:
            choice_idx = int(raw) - 1
            if 0 <= choice_idx < len(models):
                selected_model = models[choice_idx]
            else:
                warning("Invalid selection. Try again.")
        except ValueError:
            warning("Please enter a number.")

    select_model(selected_model)
    success(f"Using model: {selected_model}")
    return selected_model


def ensure_song_library() -> bool:
    """
    Ensures the Songs directory contains at least one usable audio file.

    Returns:
        ready (bool): True when audio files are available.
    """
    fetch_songs()

    songs_dir = os.path.join(ROOT_DIR, "Songs")
    if not os.path.isdir(songs_dir):
        error("Songs directory is missing. Configure zip_url or place audio files in Songs/.")
        return False

    supported_extensions = (".mp3", ".wav", ".m4a", ".aac", ".ogg")
    has_audio = any(
        os.path.isfile(os.path.join(songs_dir, name))
        and name.lower().endswith(supported_extensions)
        for name in os.listdir(songs_dir)
    )

    if not has_audio:
        error("No songs are available. Add audio files to Songs/ or configure zip_url.")
        return False

    return True


def get_account_browser_profile(account: dict) -> str:
    """
    Returns the account browser profile path with legacy Firefox fallback.

    Args:
        account (dict): Account payload

    Returns:
        path (str): Browser profile path
    """
    return account.get("browser_profile") or account.get("firefox_profile", "")


def run_scheduler(command: list[str], scheduler_options: list[str], label: str) -> None:
    """
    Runs the selected schedule in the foreground until interrupted.

    Args:
        command (list[str]): Command to run
        scheduler_options (list[str]): Times to execute each day
        label (str): Label for logs

    Returns:
        None
    """
    scheduler = schedule.Scheduler()

    def job():
        subprocess.run(command, check=False)

    for schedule_time in scheduler_options:
        scheduler.every().day.at(schedule_time).do(job)

    success(f"{label} scheduler started. Keep this process running. Press Ctrl+C to stop.")

    try:
        while True:
            scheduler.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        warning(f"{label} scheduler stopped.", False)


def main():
    """Main entry point for the application, providing a menu-driven interface
    to manage YouTube, Twitter, Affiliate Campaigns, and Outreach tasks.

    This function allows users to:
    1. Start the YouTube Shorts Studio to manage YouTube accounts,
       generate and upload videos, and run scheduled jobs.
    2. Start Twitter/X automation to manage accounts, post tweets, and
       run scheduled jobs.
    3. Manage affiliate campaigns by creating pitches and sharing them via
       Twitter accounts.
    4. Initiate an Outreach process for engagement and promotion tasks.
    5. Exit the application.

    The function continuously prompts users for input, validates it, and 
    executes the selected option until the user chooses to quit.

    Args:
        None

    Returns:
        None"""

    # Get user input
    # user_input = int(question("Select an option: "))
    valid_input = False
    while not valid_input:
        try:
    # Show user options
            info("\n============ OPTIONS ============", False)

            for idx, option in enumerate(OPTIONS):
                print(colored(f" {idx + 1}. {option}", "cyan"))

            info("=================================\n", False)
            user_input = input("Select an option: ").strip()
            if user_input == '':
                print("\n" * 100)
                raise ValueError("Empty input is not allowed.")
            user_input = int(user_input)
            valid_input = True
        except ValueError as e:
            print("\n" * 100)
            print(f"Invalid input: {e}")


    # Start the selected option
    if user_input == 1:
        info("Starting YouTube Shorts Studio...")

        cached_accounts = get_accounts("youtube")

        if len(cached_accounts) == 0:
            warning("No accounts found in cache. Create one now?")
            user_input = question("Yes/No: ")

            if user_input.lower() == "yes":
                generated_uuid = str(uuid4())

                success(f" => Generated ID: {generated_uuid}")
                nickname = question(" => Enter a nickname for this account: ")
                fp_profile = question(" => Enter the path to the Chrome user data directory: ")
                niche = question(" => Enter the account niche: ")
                language = question(" => Enter the account language: ")

                account_data = {
                    "id": generated_uuid,
                    "nickname": nickname,
                    "browser_profile": fp_profile,
                    "niche": niche,
                    "language": language,
                    "videos": [],
                }

                add_account("youtube", account_data)

                success("Account configured successfully!")
        else:
            table = PrettyTable()
            table.field_names = ["ID", "UUID", "Nickname", "Niche"]

            for account in cached_accounts:
                table.add_row([cached_accounts.index(account) + 1, colored(account["id"], "cyan"), colored(account["nickname"], "blue"), colored(account["niche"], "green")])

            print(table)
            info("Type 'd' to delete an account.", False)

            user_input = question("Select an account to start (or 'd' to delete): ").strip()

            if user_input.lower() == "d":
                delete_input = question("Enter account number to delete: ").strip()
                account_to_delete = None

                for account in cached_accounts:
                    if str(cached_accounts.index(account) + 1) == delete_input:
                        account_to_delete = account
                        break

                if account_to_delete is None:
                    error("Invalid account selected. Please try again.", "red")
                else:
                    confirm = question(f"Are you sure you want to delete '{account_to_delete['nickname']}'? (Yes/No): ").strip().lower()

                    if confirm == "yes":
                        remove_account("youtube", account_to_delete["id"])
                        success("Account removed successfully!")
                    else:
                        warning("Account deletion canceled.", False)

                return

            selected_account = None

            for account in cached_accounts:
                if str(cached_accounts.index(account) + 1) == user_input:
                    selected_account = account

            if selected_account is None:
                error("Invalid account selected. Please try again.", "red")
                return
            else:
                youtube = YouTube(
                    selected_account["id"],
                    selected_account["nickname"],
                    get_account_browser_profile(selected_account),
                    selected_account["niche"],
                    selected_account["language"]
                )

                try:
                    while True:
                        rem_temp_files()
                        info("\n============ OPTIONS ============", False)

                        for idx, youtube_option in enumerate(YOUTUBE_OPTIONS):
                            print(colored(f" {idx + 1}. {youtube_option}", "cyan"))

                        info("=================================\n", False)

                        # Get user input
                        user_input = int(question("Select an option: "))

                        if user_input == 1:
                            if ensure_model_selected() is None:
                                continue
                            if not ensure_song_library():
                                continue
                            tts = TTS()
                            youtube.generate_video(tts)
                            upload_to_yt = question("Do you want to upload this video to YouTube? (Yes/No): ")
                            if upload_to_yt.lower() == "yes":
                                youtube.upload_video()
                        elif user_input == 2:
                            videos = youtube.get_videos()

                            if len(videos) > 0:
                                videos_table = PrettyTable()
                                videos_table.field_names = ["ID", "Date", "Title"]

                                for video in videos:
                                    videos_table.add_row([
                                        videos.index(video) + 1,
                                        colored(video["date"], "blue"),
                                        colored(video["title"][:60] + "...", "green")
                                    ])

                                print(videos_table)
                            else:
                                warning(" No videos found.")
                        elif user_input == 3:
                            info("How often do you want to upload?")

                            info("\n============ OPTIONS ============", False)
                            for idx, cron_option in enumerate(YOUTUBE_CRON_OPTIONS):
                                print(colored(f" {idx + 1}. {cron_option}", "cyan"))

                            info("=================================\n", False)

                            user_input = int(question("Select an Option: "))

                            if ensure_model_selected() is None:
                                continue
                            if not ensure_song_library():
                                continue

                            cron_script_path = os.path.join(ROOT_DIR, "src", "cron.py")
                            command = [sys.executable, cron_script_path, "youtube", selected_account['id'], get_active_model()]

                            if user_input == 1:
                                run_scheduler(command, ["10:00"], "YouTube")
                            elif user_input == 2:
                                run_scheduler(command, ["10:00", "16:00"], "YouTube")
                            elif user_input == 3:
                                run_scheduler(command, ["08:00", "12:00", "18:00"], "YouTube")
                            else:
                                break
                        elif user_input == 4:
                            if get_verbose():
                                info(" => Climbing Options Ladder...", False)
                            break
                        else:
                            warning("Invalid option selected. Please try again.", False)
                finally:
                    youtube.close()
    elif user_input == 2:
        info("Starting Twitter/X Automation...")

        cached_accounts = get_accounts("twitter")

        if len(cached_accounts) == 0:
            warning("No accounts found in cache. Create one now?")
            user_input = question("Yes/No: ")

            if user_input.lower() == "yes":
                generated_uuid = str(uuid4())

                success(f" => Generated ID: {generated_uuid}")
                nickname = question(" => Enter a nickname for this account: ")
                fp_profile = question(" => Enter the path to the Chrome user data directory: ")
                topic = question(" => Enter the account topic: ")

                add_account("twitter", {
                    "id": generated_uuid,
                    "nickname": nickname,
                    "browser_profile": fp_profile,
                    "topic": topic,
                    "posts": []
                })
        else:
            table = PrettyTable()
            table.field_names = ["ID", "UUID", "Nickname", "Account Topic"]

            for account in cached_accounts:
                table.add_row([cached_accounts.index(account) + 1, colored(account["id"], "cyan"), colored(account["nickname"], "blue"), colored(account["topic"], "green")])

            print(table)
            info("Type 'd' to delete an account.", False)

            user_input = question("Select an account to start (or 'd' to delete): ").strip()

            if user_input.lower() == "d":
                delete_input = question("Enter account number to delete: ").strip()
                account_to_delete = None

                for account in cached_accounts:
                    if str(cached_accounts.index(account) + 1) == delete_input:
                        account_to_delete = account
                        break

                if account_to_delete is None:
                    error("Invalid account selected. Please try again.", "red")
                else:
                    confirm = question(f"Are you sure you want to delete '{account_to_delete['nickname']}'? (Yes/No): ").strip().lower()

                    if confirm == "yes":
                        remove_account("twitter", account_to_delete["id"])
                        success("Account removed successfully!")
                    else:
                        warning("Account deletion canceled.", False)

                return

            selected_account = None

            for account in cached_accounts:
                if str(cached_accounts.index(account) + 1) == user_input:
                    selected_account = account

            if selected_account is None:
                error("Invalid account selected. Please try again.", "red")
                return
            else:
                twitter = Twitter(
                    selected_account["id"],
                    selected_account["nickname"],
                    get_account_browser_profile(selected_account),
                    selected_account["topic"],
                )

                try:
                    while True:
                        
                        info("\n============ OPTIONS ============", False)

                        for idx, twitter_option in enumerate(TWITTER_OPTIONS):
                            print(colored(f" {idx + 1}. {twitter_option}", "cyan"))

                        info("=================================\n", False)

                        # Get user input
                        user_input = int(question("Select an option: "))

                        if user_input == 1:
                            if ensure_model_selected() is None:
                                continue
                            twitter.post()
                        elif user_input == 2:
                            posts = twitter.get_posts()

                            posts_table = PrettyTable()

                            posts_table.field_names = ["ID", "Date", "Content"]

                            for post in posts:
                                posts_table.add_row([
                                    posts.index(post) + 1,
                                    colored(post["date"], "blue"),
                                    colored(post["content"][:60] + "...", "green")
                                ])

                            print(posts_table)
                        elif user_input == 3:
                            info("How often do you want to post?")

                            info("\n============ OPTIONS ============", False)
                            for idx, cron_option in enumerate(TWITTER_CRON_OPTIONS):
                                print(colored(f" {idx + 1}. {cron_option}", "cyan"))

                            info("=================================\n", False)

                            user_input = int(question("Select an Option: "))

                            if ensure_model_selected() is None:
                                continue

                            cron_script_path = os.path.join(ROOT_DIR, "src", "cron.py")
                            command = [sys.executable, cron_script_path, "twitter", selected_account['id'], get_active_model()]

                            if user_input == 1:
                                run_scheduler(command, ["10:00"], "Twitter")
                            elif user_input == 2:
                                run_scheduler(command, ["10:00", "16:00"], "Twitter")
                            elif user_input == 3:
                                run_scheduler(command, ["08:00", "12:00", "18:00"], "Twitter")
                            else:
                                break
                        elif user_input == 4:
                            if get_verbose():
                                info(" => Climbing Options Ladder...", False)
                            break
                        else:
                            warning("Invalid option selected. Please try again.", False)
                finally:
                    twitter.close()
    elif user_input == 3:
        info("Starting Affiliate Campaigns...")

        cached_products = get_products()

        if len(cached_products) == 0:
            warning("No products found in cache. Create one now?")
            user_input = question("Yes/No: ")

            if user_input.lower() == "yes":
                affiliate_link = question(" => Enter the affiliate link: ")
                twitter_uuid = question(" => Enter the Twitter Account UUID: ")

                # Find the account
                account = None
                for acc in get_accounts("twitter"):
                    if acc["id"] == twitter_uuid:
                        account = acc

                if ensure_model_selected() is None:
                    return

                if account is None:
                    error("Twitter account UUID not found. Create or select a valid account first.")
                    return

                add_product({
                    "id": str(uuid4()),
                    "affiliate_link": affiliate_link,
                    "twitter_uuid": twitter_uuid
                })

                afm = AffiliateMarketing(
                    affiliate_link,
                    get_account_browser_profile(account),
                    account["id"],
                    account["nickname"],
                    account["topic"],
                )

                try:
                    afm.generate_pitch()
                    afm.share_pitch("twitter")
                finally:
                    afm.quit()
        else:
            table = PrettyTable()
            table.field_names = ["ID", "Affiliate Link", "Twitter Account UUID"]

            for product in cached_products:
                table.add_row([cached_products.index(product) + 1, colored(product["affiliate_link"], "cyan"), colored(product["twitter_uuid"], "blue")])

            print(table)

            user_input = question("Select a product to start: ")

            selected_product = None

            for product in cached_products:
                if str(cached_products.index(product) + 1) == user_input:
                    selected_product = product

            if selected_product is None:
                error("Invalid product selected. Please try again.", "red")
                return
            else:
                # Find the account
                account = None
                for acc in get_accounts("twitter"):
                    if acc["id"] == selected_product["twitter_uuid"]:
                        account = acc

                if ensure_model_selected() is None:
                    return

                if account is None:
                    error("Twitter account linked to this product no longer exists.")
                    return

                afm = AffiliateMarketing(
                    selected_product["affiliate_link"],
                    get_account_browser_profile(account),
                    account["id"],
                    account["nickname"],
                    account["topic"],
                )

                try:
                    afm.generate_pitch()
                    afm.share_pitch("twitter")
                finally:
                    afm.quit()

    elif user_input == 4:
        info("Starting Outreach...")

        outreach = Outreach()

        outreach.start()
    elif user_input == 5:
        if get_verbose():
            print(colored(" => Quitting...", "blue"))
        sys.exit(0)
    else:
        error("Invalid option selected. Please try again.", "red")
        return
    

if __name__ == "__main__":
    # Print ASCII Banner
    print_banner()

    first_time = get_first_time_running()

    if first_time:
        print(colored("컨텐츠제작소를 처음 실행하는 것 같습니다. 작업 환경부터 준비하겠습니다.", "yellow"))

    # Setup file tree
    assert_folder_structure()

    # Remove temporary files
    rem_temp_files()

    while True:
        main()
