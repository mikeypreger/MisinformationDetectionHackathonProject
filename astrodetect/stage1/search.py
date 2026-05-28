# ─────────────────────────────────────────────
# stage1/search.py
#
# Purpose: Send an image to SerpApi (Google Lens)
# and get back a list of all known web appearances.
# This is the "spine" of the whole pipeline —
# provenance lives here.
# ─────────────────────────────────────────────

import requests                                    # for making HTTP calls to the API
import json                                        # for saving/loading JSON files
from pathlib import Path                           # for handling file paths cleanly
from dotenv import load_dotenv                     # for reading the .env file
import os                                          # for accessing environment variables
import re                                          # regex date extraction from URLs
from concurrent.futures import ThreadPoolExecutor  # parallel page fetching
from urllib.parse import urlparse                  # extract domain for source_name
from bs4 import BeautifulSoup                      # HTML parsing — pip install beautifulsoup4

# Load the .env file so SERPAPI_KEY is available as an env variable.
# Must be called before os.getenv().
load_dotenv()

# Read the API key from the environment.
# Never hardcode keys directly in code — if you push to GitHub, they get exposed.
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# Compiled once at module load — used by extract_date_from_url on every call.
_DATE_SLASH   = re.compile(r'/(\d{4})/(\d{2})/(\d{2})/')       # /2019/03/14/
_DATE_COMPACT = re.compile(r'/(\d{4})(\d{2})(\d{2})/')          # /20190314/
_DATE_PARAM   = re.compile(r'[?&]date=(\d{4}-?\d{2}-?\d{2})')  # ?date=2019-03-14


def search_image_by_url(image_url: str) -> dict:
    """
    Takes a public image URL, sends it to SerpApi Google Lens,
    and returns the full raw JSON response.

    Args:
        image_url: a publicly accessible URL pointing to the image.
                   Example: "https://example.com/photo.jpg"

    Returns:
        A dict containing everything SerpApi returned —
        exact_matches, visual_matches, metadata, etc.
    """

    # These are the query parameters SerpApi expects.
    # 'engine' tells SerpApi which search engine to use.
    # 'url' is the image we want to reverse-search.
    # 'api_key' authenticates our request.
    params = {
        "engine": "google_lens",
        "url": image_url,
        "api_key": SERPAPI_KEY,
    }

    # Make the GET request to SerpApi.
    # timeout=30 means: if no response in 30 seconds, raise an error instead of hanging forever.
    response = requests.get(
        "https://serpapi.com/search",
        params=params,
        timeout=30
    )

    # If SerpApi returned a 4xx or 5xx error code, this will raise an exception.
    # Better to crash loudly here than silently return empty results.
    response.raise_for_status()

    # Parse and return the JSON body of the response.
    return response.json()


def save_response(data: dict, filename: str):
    """
    Saves a raw API response to a local JSON file.

    Why? API calls cost quota. Once you have a response for a test image,
    save it — you can reload it instantly without hitting the API again.

    Args:
        data: the dict returned by search_image_by_url()
        filename: a name for the file, without extension. Example: "test_run_1"
    """

    # Build the full path: tests/cached_responses/test_run_1.json
    path = Path(f"tests/cached_responses/{filename}.json")

    # Write the dict to disk as formatted JSON (indent=2 makes it readable)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved to {path}")


def load_response(filename: str) -> dict:
    """
    Loads a previously saved API response from disk.

    Use this instead of calling the API again when you're
    testing the parsing logic — saves quota and is faster.

    Args:
        filename: the name you used when calling save_response()

    Returns:
        The original dict, exactly as it was saved.
    """

    path = Path(f"tests/cached_responses/{filename}.json")

    with open(path) as f:
        return json.load(f)


def parse_appearances(raw_results: dict) -> list[dict]:
    """
    Extracts a clean, uniform list of web appearances from a raw SerpApi response.

    Pulls from "exact_matches" first (higher confidence), then "visual_matches".
    Skips any item missing a URL. Date and context are left as None here —
    they get filled in later by get_date_for_appearance and get_page_context.
    """
    appearances = []

    for match_type in ("exact_matches", "visual_matches"):
        for item in raw_results.get(match_type, []):
            url = item.get("link", "")
            if not url:
                continue
            appearances.append({
                "url": url,
                "title": item.get("title", ""),
                "source_name": item.get("source", ""),
                "match_type": match_type,
                "date": None,
                "context": None,
            })

    return appearances


def extract_date_from_url(url: str) -> str | None:
    """
    Finds a publication date encoded directly in a URL string — no network needed.

    Handles three common patterns:
      /2019/03/14/      slash-separated year/month/day
      /20190314/        compact 8-digit date
      ?date=2019-03-14  explicit query parameter

    Returns ISO "YYYY-MM-DD" or None. Rejects years outside 1990-2030.
    """
    candidate = None

    m = _DATE_SLASH.search(url)
    if m:
        candidate = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    if candidate is None:
        m = _DATE_COMPACT.search(url)
        if m:
            candidate = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    if candidate is None:
        m = _DATE_PARAM.search(url)
        if m:
            raw = m.group(1).replace("-", "")   # normalize to YYYYMMDD
            candidate = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"

    if candidate and "1990-01-01" <= candidate <= "2030-12-31":
        return candidate

    return None


def extract_date_from_page(url: str) -> str | None:
    """
    Fetches a page and looks for a publication date in HTML meta tags.

    Checks in priority order: article:published_time, pubdate, date,
    datePublished, then a <time datetime> element.
    Takes only the first 10 characters so both "2019-03-14" and
    "2019-03-14T08:00:00Z" yield the same clean ISO date.

    Returns ISO "YYYY-MM-DD" or None. Never raises — any failure returns None.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Check standard meta tags in priority order.
        meta_checks = [
            ("property", "article:published_time"),
            ("name",     "pubdate"),
            ("name",     "date"),
            ("itemprop", "datePublished"),
        ]
        for attr, val in meta_checks:
            tag = soup.find("meta", attrs={attr: val})
            if tag and tag.get("content"):
                return tag["content"][:10]

        # Fallback: <time datetime="..."> element.
        time_tag = soup.find("time", attrs={"datetime": True})
        if time_tag and time_tag["datetime"]:
            return time_tag["datetime"][:10]

    except Exception:
        pass

    return None


def get_date_for_appearance(appearance: dict) -> str | None:
    """
    Returns the best available date for a single appearance.

    Tries the URL first (instant, no network), then falls back to
    fetching and parsing the page itself.
    """
    date = extract_date_from_url(appearance["url"])
    if date is None:
        date = extract_date_from_page(appearance["url"])
    return date


def find_earliest(appearances: list[dict]) -> dict | None:
    """
    Returns the appearance with the smallest (oldest) date.

    Only considers appearances that have a non-empty date within
    1990-2030. Returns None if nothing qualifies.
    """
    valid = [
        a for a in appearances
        if a.get("date") and "1990-01-01" <= a["date"] <= "2030-12-31"
    ]
    if not valid:
        return None
    return min(valid, key=lambda a: a["date"])


def get_page_context(url: str) -> dict:
    """
    Fetches a page and extracts human-readable context: title, description, source.

    For description, tries og:description first, then the first paragraph
    longer than 80 characters (capped at 400 chars).
    Returns an empty-string fallback dict if anything goes wrong.
    """
    fallback = {"title": "", "description": "", "source_name": ""}
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        description = ""
        og_desc = soup.find("meta", attrs={"property": "og:description"})
        if og_desc and og_desc.get("content"):
            description = og_desc["content"]
        else:
            for p in soup.find_all("p"):
                text = p.get_text(strip=True)
                if len(text) > 80:
                    description = text[:400]
                    break

        netloc = urlparse(url).netloc
        source_name = netloc[4:] if netloc.startswith("www.") else netloc

        return {"title": title, "description": description, "source_name": source_name}

    except Exception:
        return fallback


def run_stage1(image_url: str) -> dict:
    """
    Main entry point for Stage 1. Takes an image URL and returns the
    earliest known web appearance with full context.

    Flow:
      1. Reverse-search the image via SerpApi Google Lens.
      2. Parse the response into a clean appearances list.
      3. Fetch dates for ALL appearances in parallel (10 threads).
      4. Find the oldest dated appearance.
      5. Enrich it with page context (title, description, source).

    Returns a dict with keys: earliest_appearance, all_appearances,
    search_confidence ("high" | "low" | "no_results").
    """
    raw_results = search_image_by_url(image_url)
    appearances = parse_appearances(raw_results)

    if not appearances:
        return {
            "earliest_appearance": None,
            "all_appearances": [],
            "search_confidence": "no_results",
        }

    # Fetch dates for all pages in parallel — 10x faster than sequential.
    with ThreadPoolExecutor(max_workers=10) as executor:
        dates = list(executor.map(get_date_for_appearance, appearances))
    for appearance, date in zip(appearances, dates):
        appearance["date"] = date

    earliest = find_earliest(appearances)

    # Enrich the earliest appearance with readable context.
    if earliest is not None:
        ctx = get_page_context(earliest["url"])
        if not earliest.get("title"):
            earliest["title"] = ctx["title"]
        if not earliest.get("context"):
            earliest["context"] = ctx["description"]
        if not earliest.get("source_name"):
            earliest["source_name"] = ctx["source_name"]

    has_any_date = any(a.get("date") for a in appearances)
    search_confidence = "high" if has_any_date else "low"

    if earliest is not None:
        return {
            "earliest_appearance": {
                "url": earliest["url"],
                "date": earliest["date"],
                "title": earliest.get("title", ""),
                "context": earliest.get("context", ""),
                "source_name": earliest.get("source_name", ""),
                "match_type": earliest["match_type"],
            },
            "all_appearances": appearances,
            "search_confidence": search_confidence,
        }

    return {
        "earliest_appearance": None,
        "all_appearances": appearances,
        "search_confidence": "low",
    }


# ─────────────────────────────────────────────
# Run Stage 1 end-to-end from the command line.
# NOTE: tests/cached_responses must be a directory, not a file.
# If you hit an error on the mkdir line, delete the 0-byte file at
# astrodetect/tests/cached_responses and re-run — mkdir will recreate
# it as a proper folder.
# ─────────────────────────────────────────────
if __name__ == "__main__":

    url = input("Paste image URL: ")
    result = run_stage1(url)

    earliest = result["earliest_appearance"]
    print(f"\nSearch confidence: {result['search_confidence']}")

    if earliest:
        print(f"Earliest URL:  {earliest['url']}")
        print(f"Date:          {earliest['date']}")
        print(f"Source:        {earliest['source_name']}")
    else:
        print("No dateable appearance found.")

    out_path = Path("tests/cached_responses/stage1_result.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nFull result saved to {out_path}")
