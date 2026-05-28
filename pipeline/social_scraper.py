"""
social_scraper.py  —  integrated

Replaces the monolithic _extract_fields() fallback chain with data_parser's
platform-specific parsers. Each parser was written to match Bright Data's
exact per-platform JSON schema, so extraction is more reliable than the
generic field-scan approach.

The public API is unchanged: scrape_post() returns
    {"image_url": str|None, "caption": str, "raw_data": dict|list}
"""

import os
import time
import requests
from dotenv import load_dotenv

# Import the platform-specific image-URL parsers from your friend's module
from data_parser import (
    parse_instagram,
    parse_facebook,
    parse_x,
    parse_reddit,
    parse_tiktok,
)

load_dotenv()

_TOKEN = os.getenv("BRIGHT_DATA_TOKEN")
_BASE  = "https://api.brightdata.com/datasets/v3"

SCRAPER_MAP = {
    "instagram": os.getenv("ID_INSTAGRAM"),
    "twitter":   os.getenv("ID_TWITTER"),
    "tiktok":    os.getenv("ID_TIKTOK"),
    "facebook":  os.getenv("ID_FACEBOOK"),
    "reddit":    os.getenv("ID_REDDIT"),
}

# Map platform keys to their dedicated data_parser function
_PARSER_MAP = {
    "instagram": parse_instagram,
    "twitter":   parse_x,
    "tiktok":    parse_tiktok,
    "facebook":  parse_facebook,
    "reddit":    parse_reddit,
}

_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")
_PROFILE_IMAGE_TOKENS = ("/profile_images/", "_normal.", "_400x400.")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_TOKEN}",
        "Content-Type": "application/json",
    }


def _trigger_scrape(dataset_id: str, url: str) -> str | None:
    """POST trigger endpoint. Returns snapshot_id or None on failure."""
    endpoint = f"{_BASE}/trigger?dataset_id={dataset_id}&include_errors=true"
    try:
        resp = requests.post(endpoint, headers=_headers(), json=[{"url": url}], timeout=30)
        resp.raise_for_status()
        return resp.json().get("snapshot_id")
    except Exception as e:
        print(f"[social_scraper] trigger failed: {e}")
        return None


def _poll_snapshot(snapshot_id: str, timeout: int = 120, interval: int = 5) -> list | None:
    """Poll until snapshot is ready. Returns list of records or None."""
    poll_url = f"{_BASE}/snapshot/{snapshot_id}?format=json"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(poll_url, headers=_headers(), timeout=30)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 202:
                time.sleep(interval)
            else:
                print(f"[social_scraper] poll unexpected status {resp.status_code}")
                return None
        except Exception as e:
            print(f"[social_scraper] poll error: {e}")
            return None
    print(f"[social_scraper] poll timed out after {timeout}s")
    return None


def _extract_caption(record: dict) -> str:
    """Pull the best caption/text field from a Bright Data record."""
    for field in ("caption", "text", "content", "title", "description"):
        val = record.get(field)
        if val and isinstance(val, str):
            return val
    return ""


def _extract_fields(record: dict, platform_key: str) -> tuple[str | None, str]:
    """
    Use the platform-specific data_parser for image URL extraction,
    with a generic URL-scan fallback for unknown platforms.

    Returns (image_url, caption).
    """
    caption   = _extract_caption(record)
    image_url = None

    parser = _PARSER_MAP.get(platform_key)
    if parser:
        # Only accept direct image URLs from the parser (not t.co shortened links)
        for url in parser(record):
            if isinstance(url, str) and any(
                url.lower().split("?")[0].endswith(ext) for ext in _IMAGE_EXTENSIONS
            ):
                image_url = url
                break

    # Generic fallback: scan string values AND one level into list values.
    # Bright Data Twitter returns images in "photos": [...] (a list), not a flat string.
    # Skips profile/avatar URLs which appear on every record.
    if image_url is None:
        for v in record.values():
            candidates = [v] if isinstance(v, str) else (v if isinstance(v, list) else [])
            for candidate in candidates:
                if (
                    isinstance(candidate, str)
                    and candidate.startswith("http")
                    and any(candidate.lower().split("?")[0].endswith(ext) for ext in _IMAGE_EXTENSIONS)
                    and not any(tok in candidate for tok in _PROFILE_IMAGE_TOKENS)
                ):
                    image_url = candidate
                    break
            if image_url:
                break

    if image_url is None:
        print(
            f"[social_scraper] could not extract image. "
            f"Record keys: {list(record.keys())} | Sample: {str(record)[:300]}"
        )

    return image_url, caption


def scrape_post(normalized_url: str, platform_key: str) -> dict:
    """
    Scrape a social media post via Bright Data.
    Returns {"image_url": str|None, "caption": str, "raw_data": dict|list}
    """
    empty = {"image_url": None, "caption": "", "raw_data": {}}

    dataset_id = SCRAPER_MAP.get(platform_key)
    if not dataset_id:
        print(f"[social_scraper] no dataset ID for platform: {platform_key}")
        return empty

    snapshot_id = _trigger_scrape(dataset_id, normalized_url)
    if not snapshot_id:
        return empty

    records = _poll_snapshot(snapshot_id)
    if not records:
        return empty

    record = records[0] if isinstance(records, list) else records
    if not isinstance(record, dict):
        return empty

    image_url, caption = _extract_fields(record, platform_key)
    return {"image_url": image_url, "caption": caption, "raw_data": record}