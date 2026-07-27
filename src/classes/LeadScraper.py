"""
LeadScraper — collects local business leads (phone numbers as primary key)
via google-maps-scraper (Go binary) and persists them as structured JSON
so other pipelines can consume them via `get_leads()`.

Originally evolved from the Outreach/email flow; email/SMTP paths have been
removed in favor of a reusable lead data store.
"""

import csv
import glob
import io
import json
import os
import platform
import re
import shlex
import subprocess
import zipfile
from datetime import datetime
from typing import Optional

import requests

from cache import get_leads_cache_path, write_json_atomic
from config import (
    ROOT_DIR,
    get_google_maps_scraper_niche,
    get_google_maps_scraper_zip_url,
    get_scraper_timeout,
)
from status import error, info, success, warning


# ---------------------------------------------------------------------------
# Phone number normalization
#
# ★ LEARNING MODE — YOU IMPLEMENT THIS ★
#
# This function is intentionally left as a TODO because phone normalization
# is domain-specific (Korean vs US vs international formats). Your rule
# determines what "the same number" means when deduping leads.
# ---------------------------------------------------------------------------

# Rough extractor — catches most digit-and-separator phone patterns.
# You can tighten or loosen this in extract_phones_from_text() below.
PHONE_EXTRACTION_REGEX = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4}"
)


def normalize_phone(raw: str) -> Optional[str]:
    """
    Normalizes a raw phone number string to a canonical form.

    TODO (YOU — 5~10 lines of meaningful logic):
      1. Strip all non-digit characters (keep a leading '+' if present).
      2. Handle Korean formats that should all collapse to the same key:
           010-1234-5678, 0212345678, 02-123-4567, +82-10-1234-5678
      3. Reject obviously invalid numbers (< 9 digits or > 15 digits).
      4. Return None for unparseable input.
      5. Pick one canonical output format and stick with it:
            - E.164 (e.g. "+821012345678")
            - Korean dash style (e.g. "010-1234-5678")
            - Pure digits (e.g. "01012345678")

    Why this matters: the return value is used as the dedup key in the
    leads store. Inconsistent normalization will create duplicate leads
    for the same business.

    Args:
        raw (str): Raw phone candidate (possibly dirty, with spaces/dashes/text).

    Returns:
        normalized (str | None): Canonical phone string, or None if invalid.
    """
    raise NotImplementedError(
        "normalize_phone() is a Learning Mode TODO — implement in "
        "src/classes/LeadScraper.py before running the scraper."
    )


def extract_phones_from_text(text: str) -> list[str]:
    """
    Extracts and normalizes all phone-like substrings from a blob of text.

    Used as a fallback when the scraper CSV has no dedicated phone column.
    """
    candidates = PHONE_EXTRACTION_REGEX.findall(text or "")
    results: list[str] = []
    for candidate in candidates:
        try:
            normalized = normalize_phone(candidate)
        except NotImplementedError:
            raise
        if normalized:
            results.append(normalized)
    return results


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class LeadScraper:
    """
    Wraps the google-maps-scraper Go binary and stores normalized leads
    in `.mp/leads.json` for consumption by other pipelines.
    """

    def __init__(self, niche: Optional[str] = None) -> None:
        self.niche = niche or get_google_maps_scraper_niche()
        self.scraper_zip_url = get_google_maps_scraper_zip_url()
        self.scraper_timeout = get_scraper_timeout()

    # -- scraper installation --------------------------------------------

    def _find_scraper_dir(self) -> str:
        for candidate in sorted(glob.glob("google-maps-scraper-*")):
            if os.path.isdir(candidate) and os.path.exists(os.path.join(candidate, "go.mod")):
                return candidate
        return ""

    def _binary_name(self) -> str:
        return (
            "google-maps-scraper.exe"
            if platform.system() == "Windows"
            else "google-maps-scraper"
        )

    def is_go_installed(self) -> bool:
        try:
            subprocess.call(["go", "version"])
            return True
        except Exception:
            return False

    def unzip_file(self, zip_link: str) -> None:
        if self._find_scraper_dir():
            info("=> Scraper already unzipped. Skipping unzip.")
            return

        response = requests.get(zip_link)
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        for member in archive.namelist():
            if ".." in member or member.startswith("/"):
                warning(f"Skipping suspicious path in archive: {member}")
                continue
            archive.extract(member)

    def build_scraper(self) -> None:
        binary_name = self._binary_name()
        if os.path.exists(binary_name):
            info("=> Scraper already built. Skipping build.")
            return

        scraper_dir = self._find_scraper_dir()
        if not scraper_dir:
            raise FileNotFoundError(
                "Could not locate extracted google-maps-scraper directory."
            )

        subprocess.run(["go", "mod", "download"], cwd=scraper_dir, check=True)
        subprocess.run(["go", "build"], cwd=scraper_dir, check=True)

        built_binary = os.path.join(scraper_dir, binary_name)
        if not os.path.exists(built_binary):
            raise FileNotFoundError(f"Expected built scraper binary at: {built_binary}")

        os.replace(built_binary, binary_name)

    def run_scraper(self, output_csv_path: str) -> bool:
        info(" => Running scraper...")
        binary_name = self._binary_name()
        command = [os.path.join(os.getcwd(), binary_name)] + shlex.split(
            f'-input niche.txt -results "{output_csv_path}"'
        )
        try:
            result = subprocess.run(command, timeout=float(self.scraper_timeout))
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            error("=> Scraper timed out.")
            return False
        except Exception as exc:
            error(f"=> Scraper crashed: {exc}")
            return False

    # -- CSV → structured leads ------------------------------------------

    def parse_csv_to_leads(self, csv_path: str) -> list[dict]:
        """
        Reads the scraper's CSV output via DictReader (so small header
        changes in the Go tool don't break us) and returns structured
        lead dicts with normalized phone numbers.
        """
        leads: list[dict] = []

        with open(csv_path, "r", newline="", errors="ignore", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                phone_raw = (row.get("phone") or row.get("phone_number") or "").strip()

                if not phone_raw:
                    joined = " ".join(str(value) for value in row.values())
                    matches = PHONE_EXTRACTION_REGEX.findall(joined)
                    phone_raw = matches[0] if matches else ""

                if not phone_raw:
                    continue

                phone = normalize_phone(phone_raw)
                if not phone:
                    continue

                leads.append(
                    {
                        "company_name": (row.get("title") or row.get("name") or "").strip(),
                        "phone": phone,
                        "address": (row.get("address") or "").strip(),
                        "website": (row.get("website") or "").strip(),
                        "category": (row.get("category") or "").strip(),
                        "niche": self.niche,
                        "scraped_at": datetime.now().isoformat(timespec="seconds"),
                    }
                )

        return leads

    # -- persistence -----------------------------------------------------

    def save_leads(self, new_leads: list[dict]) -> int:
        """
        Merges new_leads into .mp/leads.json, deduping by phone number.
        Returns the count of leads that were genuinely new.
        """
        cache_path = get_leads_cache_path()
        existing: list[dict] = []

        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
                existing = payload.get("leads", []) if isinstance(payload, dict) else []

        seen_phones = {lead.get("phone") for lead in existing if lead.get("phone")}
        added = 0

        for lead in new_leads:
            phone = lead.get("phone")
            if phone and phone not in seen_phones:
                existing.append(lead)
                seen_phones.add(phone)
                added += 1

        write_json_atomic(cache_path, {"leads": existing})
        return added

    # -- top-level entry point -------------------------------------------

    def collect(self) -> int:
        """
        Ensures the Go scraper is installed, runs it against `self.niche`,
        parses the CSV, and persists normalized leads. Returns the number
        of genuinely new leads added to the store.
        """
        if not self.is_go_installed():
            error("Go is not installed. Please install go and try again.")
            return 0

        if not self.niche:
            error(
                "Scraper niche is empty. Set google_maps_scraper_niche in "
                "config.json or pass niche= to LeadScraper()."
            )
            return 0

        self.unzip_file(self.scraper_zip_url)
        self.build_scraper()

        with open("niche.txt", "w", encoding="utf-8") as handle:
            handle.write(self.niche)

        raw_csv_path = os.path.join(ROOT_DIR, ".mp", "leads_raw.csv")

        try:
            ok = self.run_scraper(raw_csv_path)
        finally:
            if os.path.exists("niche.txt"):
                os.remove("niche.txt")

        if not ok or not os.path.exists(raw_csv_path):
            error(f" => Scraper output not found at {raw_csv_path}.")
            return 0

        new_leads = self.parse_csv_to_leads(raw_csv_path)
        added = self.save_leads(new_leads)
        success(f"Collected {len(new_leads)} leads ({added} new).")
        return added


# ---------------------------------------------------------------------------
# Pull API — other pipelines import this to consume leads
#
# Example:
#     from classes.LeadScraper import get_leads
#     leads = get_leads(niche="치과 강남")
# ---------------------------------------------------------------------------

def get_leads(niche: Optional[str] = None) -> list[dict]:
    """
    Returns saved leads from .mp/leads.json.

    Args:
        niche (str | None): If provided, only leads whose `niche` field
            matches exactly are returned. Pass None to get everything.

    Returns:
        leads (list[dict]): Each lead has keys:
            company_name, phone, address, website, category, niche, scraped_at.
    """
    cache_path = get_leads_cache_path()
    if not os.path.exists(cache_path):
        return []

    with open(cache_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    all_leads = payload.get("leads", []) if isinstance(payload, dict) else []

    if niche is None:
        return all_leads

    return [lead for lead in all_leads if lead.get("niche") == niche]


def clear_leads() -> None:
    """
    Wipes the leads cache. Use when you want a fresh collection cycle.
    """
    cache_path = get_leads_cache_path()
    write_json_atomic(cache_path, {"leads": []})
