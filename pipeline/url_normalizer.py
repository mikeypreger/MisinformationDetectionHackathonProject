import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


def _detect_platform(netloc: str) -> str | None:
    netloc = netloc.lower().lstrip("www.").lstrip("m.")
    if netloc.startswith("instagram.com"):
        return "instagram"
    if netloc.startswith("x.com") or netloc.startswith("twitter.com"):
        return "twitter"
    if netloc.startswith("tiktok.com") or netloc.startswith("vm.tiktok.com"):
        return "tiktok"
    if netloc.startswith("facebook.com") or netloc.startswith("fb.watch"):
        return "facebook"
    if netloc.startswith("reddit.com"):
        return "reddit"
    return None


def _normalize_instagram(parsed) -> str:
    m = re.search(r'/(p|reel)/([A-Za-z0-9_-]+)', parsed.path)
    if not m:
        raise ValueError(f"Cannot extract Instagram post/reel from path: {parsed.path}")
    seg_type, shortcode = m.group(1), m.group(2)
    return f"https://www.instagram.com/{seg_type}/{shortcode}/"


def _normalize_twitter(parsed) -> str:
    m = re.search(r'/([^/]+)/status/(\d+)', parsed.path)
    if not m:
        raise ValueError(f"Cannot extract Twitter status ID from path: {parsed.path}")
    user, status_id = m.group(1), m.group(2)
    return f"https://x.com/{user}/status/{status_id}"


def _normalize_tiktok(parsed) -> str:
    m = re.search(r'/@([^/]+)/video/(\d+)', parsed.path)
    if not m:
        # Short redirect or unrecognized format — return as-is, scraper will handle it
        return urlunparse(parsed._replace(query="", fragment=""))
    user, video_id = m.group(1), m.group(2)
    return f"https://www.tiktok.com/@{user}/video/{video_id}"


def _normalize_facebook(parsed) -> str:
    qs = parse_qs(parsed.query)
    if "fbid" in qs:
        fbid = qs["fbid"][0]
        return f"https://m.facebook.com/photo?fbid={fbid}"
    # Match both numeric IDs and modern pfbid alphanumeric IDs
    m = re.search(r'/posts/([A-Za-z0-9_-]+)', parsed.path)
    if m:
        page = parsed.path.split("/posts/")[0].lstrip("/")
        return f"https://m.facebook.com/{page}/posts/{m.group(1)}"
    m = re.search(r'/videos/(\d+)', parsed.path)
    if m:
        return f"https://m.facebook.com/videos/{m.group(1)}"
    # Fallback: switch to mobile domain and strip params
    return urlunparse(parsed._replace(netloc="m.facebook.com", query="", fragment=""))


def _normalize_reddit(parsed) -> str:
    m = re.search(r'/r/([^/]+)/comments/([A-Za-z0-9]+)', parsed.path)
    if not m:
        raise ValueError(f"Cannot extract Reddit post from path: {parsed.path}")
    sub, post_id = m.group(1), m.group(2)
    return f"https://www.reddit.com/r/{sub}/comments/{post_id}/"


def normalize_url(raw_url: str) -> tuple[str, str]:
    """
    Returns (normalized_url, platform_key).
    platform_key: "instagram" | "twitter" | "tiktok" | "facebook" | "reddit"
    Raises ValueError for unrecognized or malformed URLs.
    """
    raw_url = raw_url.strip()
    if not raw_url.startswith(("http://", "https://")):
        raw_url = "https://" + raw_url

    parsed = urlparse(raw_url)
    platform = _detect_platform(parsed.netloc)

    if platform is None:
        raise ValueError(f"Unrecognized social media platform for URL: {raw_url}")

    normalizers = {
        "instagram": _normalize_instagram,
        "twitter": _normalize_twitter,
        "tiktok": _normalize_tiktok,
        "facebook": _normalize_facebook,
        "reddit": _normalize_reddit,
    }

    normalized = normalizers[platform](parsed)
    return normalized, platform