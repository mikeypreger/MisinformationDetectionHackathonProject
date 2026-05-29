import io
import requests
from PIL import Image

# 🚨 Replace this with your friend's Bright Data credentials when ready 🚨
BRIGHT_DATA_PROXY = "http://username:password@brd.superproxy.io:22225"

def _get_robust_session(use_proxy: bool):
    """Creates a unified session with elite disguise headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/"
    })
    
    if use_proxy:
        session.proxies.update({"http": BRIGHT_DATA_PROXY, "https": BRIGHT_DATA_PROXY})
        
    return session

def robust_image_download(image_url: str, use_proxy: bool = False) -> Image.Image | None:
    """Safely downloads an image, bypassing CDNs and blocking HTML traps."""
    if not image_url or image_url.startswith("data:"):
        return None
        
    try:
        session = _get_robust_session(use_proxy)
        resp = session.get(image_url, timeout=15, stream=True)
        resp.raise_for_status()
        
        if 'text/html' in resp.headers.get('Content-Type', ''):
            print(f"❌ Network Guardrail: Server returned a webpage instead of an image for {image_url}")
            return None
            
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        if min(img.size) < 80: # Reject tiny tracking pixels
            return None
            
        return img
    except Exception as e:
        print(f"❌ Image Download Error: {e}")
        return None

def robust_html_fetch(page_url: str, use_proxy: bool = False) -> str | None:
    """Safely fetches HTML text for parsing og:images and meta tags."""
    if not page_url:
        return None

    try:
        session = _get_robust_session(use_proxy)
        resp = session.get(page_url, timeout=15, allow_redirects=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            print(f"⚠️  HTML Fetch: unexpected Content-Type '{content_type}' for {page_url} — skipping")
            return None

        return resp.text
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTML Fetch HTTP {e.response.status_code} for {page_url}")
        return None
    except requests.exceptions.Timeout:
        print(f"❌ HTML Fetch Timeout for {page_url}")
        return None
    except Exception as e:
        print(f"❌ HTML Fetch Error for {page_url}: {e}")
        return None