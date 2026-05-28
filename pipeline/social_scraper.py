import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

_TOKEN = os.getenv("BRIGHT_DATA_TOKEN")
_BASE = "https://api.brightdata.com/datasets/v3"

SCRAPER_MAP = {
    "instagram": os.getenv("ID_INSTAGRAM"),
    "twitter":   os.getenv("ID_TWITTER"),
    "tiktok":    os.getenv("ID_TIKTOK"),
    "facebook":  os.getenv("ID_FACEBOOK"),
    "reddit":    os.getenv("ID_REDDIT"),
}


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
        data = resp.json()
        return data.get("snapshot_id")
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


def _extract_fields(record: dict) -> tuple[str | None, str]:
    """Extract (image_url, caption) from a single record with modern schemas."""
    caption = ""
    for field in ("caption", "text", "content", "title", "description"):
        val = record.get(field)
        if val and isinstance(val, str):
            caption = val
            break

    image_url = None
    # PATCH: Added "post_image" to the flat lookup fields sequence
    for field in ("post_image", "display_url", "image_url", "media_url", "thumbnail_url",
                  "image", "photo_url", "cover_image"):
        val = record.get(field)
        if val and isinstance(val, str) and val.startswith("http"):
            image_url = val
            break

    # PATCH: Added "attachments" array processing into the nested parser fallback
    if image_url is None:
        for gallery_field in ("attachments", "media_gallery", "images", "media"):
            gallery = record.get(gallery_field)
            if isinstance(gallery, list) and gallery:
                first = gallery[0]
                if isinstance(first, dict):
                    for f in ("url", "display_url", "image_url", "src"):
                        v = first.get(f)
                        if v and isinstance(v, str) and v.startswith("http"):
                            image_url = v
                            break
                elif isinstance(first, str) and first.startswith("http"):
                    image_url = first
                if image_url:
                    break

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

    # Records is a list; take first valid one
    record = records[0] if isinstance(records, list) else records
    if not isinstance(record, dict):
        return empty

    image_url, caption = _extract_fields(record)
    return {"image_url": image_url, "caption": caption, "raw_data": record}
