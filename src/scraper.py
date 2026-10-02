from dataclasses import dataclass
import json
import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse, urlunparse
import requests

logger = logging.getLogger(__name__)


@dataclass
class FacebookPost:
    post_id: str
    url: str
    creation_time: Optional[int] = None
    message: Optional[str] = None


class FacebookScraper:
    def __init__(self, cookies: Optional[Dict[str, str]] = None):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        if cookies:
            self.session.cookies.update(cookies)

    @staticmethod
    def clean_url(raw_url: str) -> str:
        """Remove Facebook tracking and session parameters from URLs."""
        if not raw_url:
            return ""
        unescaped = raw_url.replace(r"\/", "/")
        parsed = urlparse(unescaped)
        # Keep clean scheme, netloc, path
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

    def scrape_page(self, page_url: str) -> List[FacebookPost]:
        """
        Fetch a Facebook page and extract recent posts without launching a browser.
        Returns a list of FacebookPost sorted with newest first.
        """
        clean_page_base = page_url.rstrip("/")
        try:
            resp = self.session.get(page_url, timeout=15, allow_redirects=True)
            if resp.status_code != 200:
                logger.warning(
                    f"HTTP {resp.status_code} when accessing {page_url}"
                )
                return []
            text = resp.text
        except Exception as e:
            logger.error(f"Error fetching {page_url}: {e}")
            return []

        posts_by_id: Dict[str, dict] = {}

        # 1. Parse JSON from ScheduledServerJS / Relay Modern scripts
        scripts = re.findall(r"<script[^>]*>(.*?)</script>", text, re.DOTALL)

        def traverse(obj):
            if isinstance(obj, dict):
                pid = obj.get("post_id")
                if pid:
                    pid = str(pid)
                    if pid not in posts_by_id:
                        posts_by_id[pid] = {
                            "post_id": pid,
                            "url": None,
                            "creation_time": None,
                            "message": None,
                        }

                    # Extract permalink
                    raw_perm = obj.get("permalink_url") or obj.get("wwwURL")
                    if raw_perm and not posts_by_id[pid]["url"]:
                        posts_by_id[pid]["url"] = self.clean_url(raw_perm)

                    # Extract creation timestamp
                    ctime = obj.get("creation_time")
                    if ctime and not posts_by_id[pid]["creation_time"]:
                        try:
                            posts_by_id[pid]["creation_time"] = int(ctime)
                        except (ValueError, TypeError):
                            pass

                    # Extract text message
                    msg_obj = obj.get("message")
                    if isinstance(msg_obj, dict) and msg_obj.get("text"):
                        if not posts_by_id[pid]["message"]:
                            posts_by_id[pid]["message"] = msg_obj["text"]

                for v in obj.values():
                    traverse(v)
            elif isinstance(obj, list):
                for item in obj:
                    traverse(item)

        for s in scripts:
            if "post_id" in s:
                try:
                    data = json.loads(s)
                    traverse(data)
                except Exception:
                    pass

        # 2. Regex fallback: Find permalink_urls directly in text if any
        found_permalinks = re.findall(
            r'\"permalink_url\":\"([^\"]+)\"', text
        )
        for raw_link in found_permalinks:
            clean_link = self.clean_url(raw_link)
            # Match post ID or pfbid from link
            match = re.search(r"/(?:posts|videos|reel)/([^/?]+)", clean_link)
            if match:
                link_id = match.group(1)
                # If not recorded under this id, add it
                matched_existing = False
                for p in posts_by_id.values():
                    if p.get("url") == clean_link:
                        matched_existing = True
                        break
                if not matched_existing:
                    posts_by_id[link_id] = {
                        "post_id": link_id,
                        "url": clean_link,
                        "creation_time": None,
                        "message": None,
                    }

        # 3. Construct FacebookPost objects
        results: List[FacebookPost] = []
        for pid, data in posts_by_id.items():
            post_url = data["url"] or f"{clean_page_base}/posts/{pid}"
            # Ignore root page links or invalid IDs
            if post_url == clean_page_base or len(pid) < 4:
                continue

            results.append(
                FacebookPost(
                    post_id=pid,
                    url=post_url,
                    creation_time=data["creation_time"],
                    message=data["message"],
                )
            )

        # Sort posts: newest first (items with timestamps first, then others)
        results.sort(
            key=lambda x: (x.creation_time or 0),
            reverse=True,
        )
        return results
