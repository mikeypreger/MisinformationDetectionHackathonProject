# ─────────────────────────────────────────────
# stage1/search.py
#
# Purpose: Send an image to SerpApi (Google Lens)
# and get back a list of all known web appearances.
# ─────────────────────────────────────────────

import sys
from pathlib import Path

# Ensure project root is on sys.path so root-level modules (utils_network, etc.) are importable
# regardless of where Python is launched from.
current_file = Path(__file__).resolve()
_PROJECT_ROOT = str(current_file.parent.parent)  # pipeline/ -> project root
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import requests                                    
import json                                        
import os                                          
import re                                          
from concurrent.futures import ThreadPoolExecutor  
from urllib.parse import urlparse                  
from bs4 import BeautifulSoup                      
from dotenv import load_dotenv

# Now Python knows where to find this!
from utils_network import robust_html_fetch        

# Load the .env file so SERPAPI_KEY is available as an env variable.
load_dotenv()

# Read the API key from the environment.
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# Absolute path to the cache directory, anchored to this file's location.
_CACHE_DIR = Path(__file__).resolve().parent.parent / "tests" / "cached_responses"

# Compiled once at module load — used by extract_date_from_url on every call.
_DATE_SLASH   = re.compile(r'/(\d{4})/(\d{2})/(\d{2})/')       # /2019/03/14/
_DATE_COMPACT = re.compile(r'/(\d{4})(\d{2})(\d{2})/')          # /20190314/
_DATE_PARAM   = re.compile(r'[?&]date=(\d{4}-?\d{2}-?\d{2})')  # ?date=2019-03-14


def search_image_by_url(image_url: str) -> dict:
    """
    Takes a public image URL, sends it to SerpApi Google Lens,
    and returns the full raw JSON response.
    """
    params = {
        "engine": "google_lens",
        "url": image_url,
        "api_key": SERPAPI_KEY,
    }

    # SerpApi expects automated traffic, so a standard request is perfectly fine here.
    response = requests.get(
        "https://serpapi.com/search",
        params=params,
        timeout=30
    )
    response.raise_for_status()
    return response.json()


def save_response(data: dict, filename: str):
    """Saves a raw API response to a local JSON file."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _CACHE_DIR / f"{filename}.json"

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved to {path}")


def load_response(filename: str) -> dict:
    """Loads a previously saved API response from disk."""
    path = _CACHE_DIR / f"{filename}.json"
    with open(path) as f:
        return json.load(f)


def parse_appearances(raw_results: dict) -> list[dict]:
    """Extracts a clean, uniform list of web appearances from a raw SerpApi response."""
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
    """Finds a publication date encoded directly in a URL string."""
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
    """Fetches a page and looks for a publication date in HTML meta tags."""
    try:
        # 🚨 Route through our robust fetcher to bypass blocks
        html_text = robust_html_fetch(url, use_proxy=False)
        if not html_text:
            return None
            
        soup = BeautifulSoup(html_text, "html.parser")

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

        time_tag = soup.find("time", attrs={"datetime": True})
        if time_tag and time_tag["datetime"]:
            return time_tag["datetime"][:10]

    except Exception:
        pass

    return None


def get_date_for_appearance(appearance: dict) -> str | None:
    """Returns the best available date for a single appearance."""
    date = extract_date_from_url(appearance["url"])
    if date is None:
        date = extract_date_from_page(appearance["url"])
    return date


def find_earliest(appearances: list[dict]) -> dict | None:
    """
    Returns the appearance with the oldest date after filtering out 
    irrelevant visual noise using an algorithmic text-consensus layer.
    """
    valid = [
        a for a in appearances
        if a.get("date") and "1990-01-01" <= a["date"] <= "2030-12-31"
    ]
    if not valid:
        return None

    # 1. STRICT PRIORITY: If Google Lens flags literal exact matches, use them first
    exacts = [a for a in valid if a.get("match_type") == "exact_matches"]
    if exacts:
        return min(exacts, key=lambda a: a["date"])

    # 2. CONSENSUS FILTER: Stop random old visual noise from hijacking the timeline
    stop_words = {
        "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "with", "by", "of", "from", 
        "is", "are", "was", "were", "th", "to", "as", "into", "about", "that", "this", "http", "https",
        "youtube", "video", "twitter", "x.com"
    }
    
    # Build a global frequency map of words across ALL retrieved titles to discover the real topic
    word_counts = {}
    for a in appearances:
        title = a.get("title", "").lower()
        words = re.findall(r'[a-z0-9]+', title)
        for w in set(words):  # Deduplicate per title
            if w not in stop_words and len(w) > 1:
                word_counts[w] = word_counts.get(w, 0) + 1

    if not word_counts:
        return min(valid, key=lambda a: a["date"])

    # Score each dated appearance based on how well it aligns with the global pool's vocabulary
    scored_appearances = []
    for a in valid:
        title = a.get("title", "").lower()
        words = re.findall(r'[a-z0-9]+', title)
        score = sum(word_counts.get(w, 0) for w in set(words) if w in word_counts)
        scored_appearances.append((score, a))

    # Sort by consensus score descending
    scored_appearances.sort(key=lambda x: x[0], reverse=True)
    max_score = scored_appearances[0][0]

    # Aggressively drop any links that score less than 40% of the top consensus score
    # This purges outlier junk (like a 2017 Libya article when the pool is 95% Gaza 2026)
    threshold = max_score * 0.4
    filtered_valid = [a for score, a in scored_appearances if score >= threshold]

    if not filtered_valid:
        return min(valid, key=lambda a: a["date"])

    # Return the oldest date among the mathematically verified topic matches
    return min(filtered_valid, key=lambda a: a["date"])

def get_page_context(url: str) -> dict:
    """Fetches a page and extracts human-readable context: title, description, source."""
    fallback = {"title": "", "description": "", "source_name": ""}
    try:
        # 🚨 Route through our robust fetcher to bypass blocks
        html_text = robust_html_fetch(url, use_proxy=False)
        if not html_text:
            return fallback
            
        soup = BeautifulSoup(html_text, "html.parser")

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


def _extract_twitter_image(tweet_url: str) -> str | None:
    """Extract first image URL from a Twitter/X tweet via the vxtwitter public API."""
    m = re.search(r'/([^/?#]+)/status/(\d+)', tweet_url)
    if not m:
        return None
    username, tweet_id = m.group(1), m.group(2)
    try:
        resp = requests.get(
            f"https://api.vxtwitter.com/{username}/status/{tweet_id}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        resp.raise_for_status()
        urls = resp.json().get("mediaURLs", [])
        return urls[0] if urls else None
    except Exception as e:
        print(f"❌ Twitter image extraction error: {e}")
        return None


def _is_direct_image_url(url: str) -> bool:
    """Returns True if the URL almost certainly points to an image file, not a web page."""
    parsed = urlparse(url)
    path = parsed.path.lower()
    image_extensions = (".jpg", ".jpeg", ".png", ".webp", ".gif")

    if path.endswith(image_extensions):
        return True

    query = parsed.query.lower()
    if any(f"format={ext.lstrip('.')}" in query for ext in image_extensions):
        return True

    image_cdns = ("pbs.twimg.com", "i.redd.it", "i.imgur.com", "i.ibb.co")
    netloc = parsed.netloc.lower()
    if any(netloc == cdn or netloc.endswith("." + cdn) for cdn in image_cdns):
        return True

    return False


def extract_image_from_post(post_url: str) -> str | None:
    """Fetches a web page and extracts the main image URL from its Open Graph / Twitter meta tags."""
    netloc = urlparse(post_url).netloc.lower()
    if "x.com" in netloc or "twitter.com" in netloc:
        return _extract_twitter_image(post_url)

    try:
        html_text = robust_html_fetch(post_url, use_proxy=False)
        if not html_text:
            return None

        soup = BeautifulSoup(html_text, "html.parser")

        meta_checks = [
            ("property", "og:image"),
            ("name",     "twitter:image"),
            ("property", "og:image:secure_url"),
        ]
        for attr, val in meta_checks:
            tag = soup.find("meta", attrs={attr: val})
            if tag and tag.get("content"):
                return tag["content"]

    except Exception:
        pass

    return None


def run_stage1(input_url: str) -> dict:
    """Main entry point for Stage 1. Accepts either a direct image URL or a post URL."""
    if _is_direct_image_url(input_url):
        image_url = input_url
        mode = "direct"
    else:
        mode = "post"
        image_url = extract_image_from_post(input_url)  

        if image_url is None:                    
            return {
                "error": "Could not extract image from this URL. Please paste a direct image URL ending in .jpg or .png",
                "earliest_appearance": None,
                "all_appearances": [],
                "search_confidence": "no_results",
                "image_url": None,
                "mode": mode,
            }

    raw_results = search_image_by_url(image_url)
    appearances = parse_appearances(raw_results)

    if not appearances:                          
        return {
            "earliest_appearance": None,
            "all_appearances": [],
            "search_confidence": "no_results",
            "image_url": image_url,
            "mode": mode,
        }

    with ThreadPoolExecutor(max_workers=10) as executor:
        dates = list(executor.map(get_date_for_appearance, appearances))  
    for appearance, date in zip(appearances, dates):  
        appearance["date"] = date                     

    earliest = find_earliest(appearances)

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
                "url":         earliest["url"],
                "date":        earliest["date"],
                "title":       earliest.get("title", ""),
                "context":     earliest.get("context", ""),
                "source_name": earliest.get("source_name", ""),
                "match_type":  earliest["match_type"],
            },
            "all_appearances": appearances,
            "search_confidence": search_confidence,
            "image_url": image_url,  
            "mode": mode,            
        }

    return {
        "earliest_appearance": None,
        "all_appearances": appearances,
        "search_confidence": "low",
        "image_url": image_url,
        "mode": mode,
    }

# ── Public API used by MyApp.py ──────────────────────────────────────────────

def run_reverse_image_search(image_url: str) -> dict:
    """
    Reverse-search image_url via SerpAPI Google Lens.
    Returns the run_stage1() result dict, which contains:
        earliest_appearance: {url, date, source_name, title, context, match_type} | None
        all_appearances:     list of dicts
        search_confidence:   "high" | "low" | "no_results"
    On any failure returns {"error": ..., "earliest_appearance": None, "all_appearances": []}.
    """
    try:
        return run_stage1(image_url)
    except Exception as e:
        print(f"[context_enricher] reverse image search failed: {e}")
        return {
            "error": str(e),
            "earliest_appearance": None,
            "all_appearances": [],
            "search_confidence": "no_results",
        }


def _gps_dms_to_decimal(dms_tuple, ref: str) -> float | None:
    try:
        deg  = dms_tuple[0][0] / dms_tuple[0][1]
        min_ = dms_tuple[1][0] / dms_tuple[1][1]
        sec  = dms_tuple[2][0] / dms_tuple[2][1]
        val  = deg + min_ / 60 + sec / 3600
        return round(-val if ref in ("S", "W") else val, 6)
    except Exception:
        return None


def _exif_via_piexif(image_bytes: bytes) -> dict:
    import piexif
    result = {"datetime_original": None, "camera_make": None,
              "camera_model": None, "gps_lat": None, "gps_lon": None}
    try:
        exif = piexif.load(image_bytes)
    except Exception:
        return result

    ifd0     = exif.get("0th", {})
    exif_ifd = exif.get("Exif", {})
    gps_ifd  = exif.get("GPS", {})

    raw = exif_ifd.get(piexif.ExifIFD.DateTimeOriginal)
    if isinstance(raw, bytes):
        result["datetime_original"] = raw.decode("utf-8", errors="ignore")

    for key, field in ((piexif.ImageIFD.Make, "camera_make"),
                       (piexif.ImageIFD.Model, "camera_model")):
        raw = ifd0.get(key)
        if isinstance(raw, bytes):
            result[field] = raw.decode("utf-8", errors="ignore").strip("\x00")

    if gps_ifd:
        lat_dms = gps_ifd.get(piexif.GPSIFD.GPSLatitude)
        lat_ref = gps_ifd.get(piexif.GPSIFD.GPSLatitudeRef)
        lon_dms = gps_ifd.get(piexif.GPSIFD.GPSLongitude)
        lon_ref = gps_ifd.get(piexif.GPSIFD.GPSLongitudeRef)
        if lat_dms and lat_ref:
            result["gps_lat"] = _gps_dms_to_decimal(
                lat_dms, lat_ref.decode() if isinstance(lat_ref, bytes) else lat_ref)
        if lon_dms and lon_ref:
            result["gps_lon"] = _gps_dms_to_decimal(
                lon_dms, lon_ref.decode() if isinstance(lon_ref, bytes) else lon_ref)
    return result


def _exif_via_pil(image_bytes: bytes) -> dict:
    from PIL import Image
    from io import BytesIO
    result = {"datetime_original": None, "camera_make": None,
              "camera_model": None, "gps_lat": None, "gps_lon": None}
    try:
        raw_exif = Image.open(BytesIO(image_bytes))._getexif()
        if raw_exif:
            result["datetime_original"] = raw_exif.get(36867)
            result["camera_make"]       = raw_exif.get(271)
            result["camera_model"]      = raw_exif.get(272)
    except Exception:
        pass
    return result


def extract_image_metadata(image_url: str) -> dict:
    """
    Download image_url and extract EXIF metadata.

    Returns dict with keys: datetime_original, camera_make, camera_model,
    gps_lat, gps_lon — all default to None if stripped or unavailable.
    """
    empty = {"datetime_original": None, "camera_make": None,
             "camera_model": None, "gps_lat": None, "gps_lon": None}
    try:
        resp = requests.get(image_url, timeout=10,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        image_bytes = resp.content
    except Exception as e:
        print(f"[context_enricher] EXIF download failed: {e}")
        return empty

    result = _exif_via_piexif(image_bytes)
    if all(v is None for v in result.values()):
        result = _exif_via_pil(image_bytes)
    return result


if __name__ == "__main__":
    url = input("Paste image or post URL: ")  

    if _is_direct_image_url(url):
        print("Direct image URL detected")
    else:
        print("Post URL detected — extracting image...")

    result = run_stage1(url)  

    if result.get("error"):
        print(f"\nError: {result['error']}")
    else:
        earliest = result["earliest_appearance"]      
        print(f"\nImage searched:    {result.get('image_url')}")
        print(f"Search confidence: {result['search_confidence']}")

        if earliest:                                  
            print(f"Earliest URL:      {earliest['url']}")
            print(f"Date:              {earliest['date']}")
            print(f"Source:            {earliest['source_name']}")
        else:                                         
            print("No dateable appearance found.")

    out_path = _CACHE_DIR / "stage1_result.json"
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)    
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)               
    print(f"\nFull result saved to {out_path}")