import io
import os
from concurrent.futures import ThreadPoolExecutor

import requests
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
_SERPAPI_BASE = "https://serpapi.com/search"

# Social platforms whose image URLs are behind login walls or unhelpful
_SKIP_SOURCES = ("reddit.com", "facebook.com", "twitter.com", "x.com",
                 "youtube.com", "instagram.com", "tiktok.com")

# Per-query image budgets, ordered most-to-least relevant (caption_extractor ranks queries).
_IMAGE_BUDGETS = {1: [60], 2: [40, 20], 3: [30, 20, 10]}

_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/16.0 Mobile/15E148 Safari/604.1"
)

_MIN_DIM = 80  # reject images smaller than this on either side


# ── SerpAPI Google Images Light ─────────────────────────────────────────────

def _extract_urls(data: dict, target: int, collected: list[str]) -> None:
    """
    Pull valid image URLs from one SerpAPI response page into `collected`.
    Skips: unsafe flagged images, images smaller than _MIN_DIM, skip-source domains.
    Stops early once len(collected) >= target.
    """
    for item in data.get("images_results", []):
        if len(collected) >= target:
            return
        if item.get("unsafe"):
            continue
        w = item.get("original_width",  _MIN_DIM + 1)
        h = item.get("original_height", _MIN_DIM + 1)
        if w < _MIN_DIM or h < _MIN_DIM:
            continue
        source = item.get("source", "")
        if any(d in source for d in _SKIP_SOURCES):
            continue
        url = item.get("original", "")
        if url and url.startswith("http") and url not in collected:
            collected.append(url)


def _fetch_one_query(query: str, target_images: int = 20) -> list[str]:
    """
    Fetch up to target_images direct image URLs via SerpAPI Google Images Light.

    Google Images Light returns ~20 results per page. Paginates at most once
    (via serpapi_pagination.next) if the first page doesn't fill the budget.
    SerpAPI is synchronous — each call resolves in ~2-4s.
    """
    params = {
        "engine": "google_images_light",
        "q": query,
        "gl": "us",
        "hl": "en",
        "api_key": SERPAPI_KEY,
    }

    urls: list[str] = []

    for page_num in range(2):  # first page + one optional follow-up
        try:
            if page_num == 0:
                resp = requests.get(_SERPAPI_BASE, params=params, timeout=30)
            else:
                next_url = data.get("serpapi_pagination", {}).get("next")  # type: ignore[name-defined]
                if not next_url:
                    break
                resp = requests.get(next_url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[image_fetcher] SerpAPI error (page {page_num}) for {query!r}: {e}")
            break

        _extract_urls(data, target_images, urls)

        if len(urls) >= target_images:
            break

    print(f"[image_fetcher] {len(urls)}/{target_images} images fetched for: {query!r}")
    return urls[:target_images]


# ── Public API ──────────────────────────────────────────────────────────────

def fetch_context_image_urls(queries: list[str], max_total: int = 60) -> list[str]:
    """
    Run all queries concurrently via SerpAPI Google Images Light, then
    merge results in priority order (Q1 most relevant → dominates pool).

    Image budgets (queries ranked most-to-least relevant by caption_extractor):
        1 query   → [60]
        2 queries → [40, 20]
        3 queries → [30, 20, 10]

    Three parallel SerpAPI calls resolve in ~4s total.
    """
    active = [q for q in queries[:3] if q and q.strip()]
    if not active:
        return []

    n = len(active)
    budgets = _IMAGE_BUDGETS.get(n, [max(1, max_total // n)] * n)
    print(f"[image_fetcher] {n} quer{'y' if n == 1 else 'ies'} | image budgets: {budgets}")

    with ThreadPoolExecutor(max_workers=n) as ex:
        image_lists = list(ex.map(
            lambda qt: _fetch_one_query(qt[0], qt[1]),
            zip(active, budgets),
        ))

    # Merge in priority order: Q1 images first; deduplicate across queries
    seen: set[str] = set()
    result: list[str] = []
    for lst in image_lists:
        for url in lst:
            if url not in seen:
                seen.add(url)
                result.append(url)
            if len(result) >= max_total:
                break
        if len(result) >= max_total:
            break

    print(f"[image_fetcher] final pool: {len(result)} unique image URLs")
    return result


# ── Image downloader ─────────────────────────────────────────────────────────

def _download_one(url: str) -> Image.Image | None:
    if not url or url.startswith("data:"):
        return None
    try:
        resp = requests.get(
            url, timeout=3,
            headers={"User-Agent": _MOBILE_UA},
            stream=True,
        )
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        if min(img.size) < _MIN_DIM:
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
