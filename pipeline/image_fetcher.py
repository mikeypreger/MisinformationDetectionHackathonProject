import io
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus

import requests
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

_TOKEN = os.getenv("BRIGHT_DATA_TOKEN")
_GOOGLE_IMAGES_ID = os.getenv("ID_GOOGLE_IMAGES")
_BASE = "https://api.brightdata.com/datasets/v3"

# Social platforms that require login or return no useful og:image
_SKIP_DOMAINS = ("reddit.com", "facebook.com", "twitter.com", "x.com",
                 "youtube.com", "instagram.com", "tiktok.com")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_TOKEN}",
        "Content-Type": "application/json",
    }


# ── Bright Data SERP fetch ──────────────────────────────────────────────────

def _trigger(url: str) -> str | None:
    """Trigger a Bright Data SERP scrape. Returns snapshot_id or None."""
    endpoint = f"{_BASE}/trigger?dataset_id={_GOOGLE_IMAGES_ID}&include_errors=true"
    try:
        resp = requests.post(endpoint, headers=_headers(), json=[{"url": url}], timeout=30)
        if resp.status_code not in (200, 201, 202):
            print(f"[image_fetcher] trigger error {resp.status_code}: {resp.text[:200]}")
            return None
        sid = resp.json().get("snapshot_id")
        print(f"[image_fetcher] snapshot_id={sid} for {url}")
        return sid
    except Exception as e:
        print(f"[image_fetcher] trigger exception: {e}")
        return None


def _poll(snapshot_id: str, timeout: int = 45, interval: int = 5) -> list | None:
    """Poll until snapshot is ready. Returns list of records or None."""
    poll_url = f"{_BASE}/snapshot/{snapshot_id}?format=json"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(poll_url, headers=_headers(), timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                n = len(data) if isinstance(data, list) else "dict"
                print(f"[image_fetcher] snapshot ready — {n} records")
                return data
            elif resp.status_code == 202:
                time.sleep(interval)
            else:
                print(f"[image_fetcher] poll error {resp.status_code}: {resp.text[:100]}")
                return None
        except Exception as e:
            print(f"[image_fetcher] poll exception: {e}")
            return None
    print(f"[image_fetcher] poll timed out after {timeout}s")
    return None


def _links_from_serp(records: list) -> list[str]:
    """
    Extract article page URLs (link field) from organic SERP results.
    Skips social platforms that don't serve useful og:images without login.
    """
    if not isinstance(records, list):
        records = [records] if isinstance(records, dict) else []

    links = []
    for i, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        organic = record.get("organic", [])
        if i == 0:
            print(f"[image_fetcher] organic results in record: {len(organic)}")
        for item in organic:
            if not isinstance(item, dict):
                continue
            link = item.get("link", "")
            if link and link.startswith("http"):
                if not any(d in link for d in _SKIP_DOMAINS):
                    links.append(link)

    print(f"[image_fetcher] scraped {len(links)} article links from SERP")
    return list(dict.fromkeys(links))  # deduplicate


def _serp_links_for_query(query: str, pages: int = 5) -> list[str]:
    """Fetch `pages` SERP result pages for a query and return article link URLs."""
    all_links: list[str] = []
    for page in range(pages):
        start = page * 10
        url = f"https://www.google.com/search?q={quote_plus(query)}&start={start}&gl=US&hl=en"
        sid = _trigger(url)
        if not sid:
            break
        records = _poll(sid)
        if not records:
            break
        page_links = _links_from_serp(records)
        all_links.extend(page_links)
        if not page_links:
            break
    return all_links


# ── og:image extraction ─────────────────────────────────────────────────────

_OG_PATTERNS = [
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\'<>]+)["\']',
    r'<meta[^>]+content=["\']([^"\'<>]+)["\'][^>]+property=["\']og:image["\']',
    r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\'<>]+)["\']',
    r'<meta[^>]+content=["\']([^"\'<>]+)["\'][^>]+name=["\']twitter:image["\']',
]

# URL path fragments that indicate a logo/brand image rather than a content photo
_LOGO_TOKENS = (
    "logo", "brand", "placeholder", "metatag", "og-image.",
    "default-image", "fallback", "favicon", "icon", "badge",
)

_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/16.0 Mobile/15E148 Safari/604.1"
)


def _is_logo_url(url: str) -> bool:
    """Return True if the URL path suggests a logo or generic site image."""
    path = url.lower().split("?")[0]
    return any(tok in path for tok in _LOGO_TOKENS)


def _og_image_from_url(page_url: str) -> str | None:
    """
    Fetch a page with a mobile User-Agent and return its og:image URL, or None.
    Uses 12KB read limit (og:image is always in <head>, within first 5KB) and
    5s timeout. Rejects extracted URLs that look like logos or generic og:images.
    """
    try:
        resp = requests.get(
            page_url, timeout=5,
            headers={"User-Agent": _MOBILE_UA},
            stream=True,
        )
        content = b""
        for chunk in resp.iter_content(chunk_size=4096):
            content += chunk
            if len(content) > 12_000:
                break
        text = content.decode("utf-8", errors="ignore")
        for pattern in _OG_PATTERNS:
            m = re.search(pattern, text, re.I | re.S)
            if m:
                img = m.group(1).strip()
                if img.startswith("http") and not _is_logo_url(img):
                    return img
    except Exception:
        pass
    return None


def _og_images_parallel(links: list[str], max_workers: int = 20) -> list[str]:
    """Fetch og:image from each link in parallel. Returns list of image URLs."""
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        results = list(ex.map(_og_image_from_url, links))
    image_urls = [r for r in results if r]
    print(f"[image_fetcher] extracted {len(image_urls)}/{len(links)} og:images")
    return image_urls


# ── Public API ──────────────────────────────────────────────────────────────

def fetch_context_image_urls(queries: list[str], max_total: int = 500) -> list[str]:
    """
    For each query:
      1. Fetch SERP results from Bright Data (multiple pages)
      2. Collect article page URLs from organic results
      3. Fetch each page's og:image in parallel
    Returns deduplicated image URLs capped at max_total.
    """
    all_image_urls: set[str] = set()

    for query in queries[:3]:
        if len(all_image_urls) >= max_total:
            break
        if not query or not query.strip():
            continue

        remaining = max_total - len(all_image_urls)
        pages = min(2, max(1, remaining // 8))  # hard cap: 2 SERP pages per query
        print(f"[image_fetcher] querying {pages} SERP pages for: {query!r}")

        links = _serp_links_for_query(query, pages=pages)
        if not links:
            print(f"[image_fetcher] no links found for {query!r}")
            continue

        image_urls = _og_images_parallel(links)
        all_image_urls.update(image_urls)
        print(f"[image_fetcher] pool size after {query!r}: {len(all_image_urls)}")

    result = list(all_image_urls)[:max_total]
    print(f"[image_fetcher] final pool: {len(result)} unique image URLs")
    return result


def _download_one(url: str) -> Image.Image | None:
    if not url or url.startswith("data:"):
        return None
    try:
        resp = requests.get(
            url, timeout=10,
            headers={"User-Agent": _MOBILE_UA},
            stream=True,
        )
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        # Reject tiny images (logos, icons) — real content photos are >= 80px on each side
        if min(img.size) < 80:
            return None
        return img
    except Exception:
        return None


def download_images_parallel(image_urls: list[str], max_workers: int = 20) -> list[Image.Image]:
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(_download_one, image_urls))
    valid = [r for r in results if r is not None]
    print(f"[image_fetcher] downloaded {len(valid)}/{len(image_urls)} images")
    return valid
