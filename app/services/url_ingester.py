"""
Web URL ingestion: fetch, clean, and index web pages.
"""
import re
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SecondBrain/1.0)"
}
TIMEOUT = 15


def _clean_html(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Remove noisy tags
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "iframe", "noscript", "form", "button"]):
        tag.decompose()

    # Prefer article / main content
    main = soup.find("article") or soup.find("main") or soup.find(id="content") or soup.body
    text = main.get_text(separator="\n") if main else soup.get_text(separator="\n")

    # Collapse whitespace
    lines = [l.strip() for l in text.splitlines()]
    lines = [l for l in lines if l]
    return "\n".join(lines)


def fetch_url(url: str) -> Optional[dict]:
    """
    Fetch a URL and return {url, title, text} or None on failure.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "text" not in content_type and "html" not in content_type:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        title_tag = soup.find("title")
        title = title_tag.get_text().strip() if title_tag else urlparse(url).netloc
        text = _clean_html(resp.text, url)

        if not text or len(text) < 100:
            return None

        return {"url": url, "title": title, "text": text}
    except Exception as e:
        raise RuntimeError(f"Failed to fetch {url}: {e}")


def url_to_filename(url: str) -> str:
    """Produce a stable, safe filename from a URL."""
    parsed = urlparse(url)
    host = re.sub(r"[^a-zA-Z0-9]", "_", parsed.netloc)
    path = re.sub(r"[^a-zA-Z0-9]", "_", parsed.path.strip("/"))
    name = f"{host}_{path}" if path else host
    return name[:80] + ".url.txt"
