"""
utils_network.py  —  Shared HTTP fetch utilities

robust_html_fetch() is the single entry point for fetching web pages
across the pipeline. Using one function here means we can add proxy
support, retries, or header rotation in one place.
"""

import requests

_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)


def robust_html_fetch(url: str, use_proxy: bool = False, timeout: int = 10) -> str | None:
    """
    Fetch a web page and return its HTML text, or None on failure.

    Tries a desktop User-Agent first; falls back to a mobile UA if the
    server returns 403 (many sites block desktop crawlers but allow mobile).

    use_proxy: reserved for future Bright Data proxy integration.
               Currently has no effect — all fetches go direct.
    """
    for ua in (_DESKTOP_UA, _MOBILE_UA):
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": ua},
                timeout=timeout,
                allow_redirects=True,
            )
            if resp.status_code == 403:
                continue  # try next UA
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.HTTPError:
            continue
        except Exception:
            return None

    return None