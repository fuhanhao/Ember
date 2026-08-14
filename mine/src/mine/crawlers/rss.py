import re
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
from readability import Document
import trafilatura

from mine.crawlers.base import BaseCrawler, CrawledItem

logger = logging.getLogger(__name__)

FETCH_TIMEOUT = 10
MIN_FULLTEXT_LEN = 200

# Tags to keep for formatting
SAFE_TAGS = {'p', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
             'ul', 'ol', 'li', 'blockquote', 'pre', 'code',
             'strong', 'b', 'em', 'i', 'a', 'img', 'figure', 'figcaption',
             'table', 'thead', 'tbody', 'tr', 'th', 'td'}


def _clean_html(html: str) -> str:
    """Keep safe formatting tags, remove scripts/styles/iframes, strip others."""
    # Remove script, style, iframe blocks entirely
    html = re.sub(r'<(script|style|iframe|noscript)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # Remove dangerous attributes (onclick, onerror, style with expression, etc)
    html = re.sub(r'\s+(on\w+|style)\s*=\s*["\'][^"\']*["\']', '', html, flags=re.IGNORECASE)
    # Remove tags not in safe list but keep their content
    def _replace_tag(m):
        tag = m.group(1).lower().split()[0].strip('/')
        if tag in SAFE_TAGS:
            return m.group(0)
        return ''
    html = re.sub(r'<(/?\s*([a-zA-Z][a-zA-Z0-9]*)[^>]*)>', lambda m: _replace_tag(m), html)
    # Collapse excessive whitespace but preserve newlines
    html = re.sub(r'[ \t]+', ' ', html)
    html = re.sub(r'\n{3,}', '\n\n', html)
    return html.strip()


class RssCrawler(BaseCrawler):
    def crawl(self) -> list[CrawledItem]:
        feed_url = self.config.get("feed_url", "")
        if not feed_url:
            return []

        feed = feedparser.parse(feed_url)
        items = []

        for entry in feed.entries:
            url = entry.get("link", "")
            title = entry.get("title", "")
            if not url or not title:
                continue

            content = self._extract_content(entry)
            author = entry.get("author")
            published_at = self._parse_date(entry)
            language = feed.feed.get("language", "en")

            # Try to fetch full text unless skip_fulltext is set
            if url and not self.config.get("skip_fulltext", False):
                fulltext = self._fetch_fulltext(url)
                if fulltext and len(fulltext) > len(content):
                    content = fulltext

            items.append(CrawledItem(
                url=url,
                title=title.strip(),
                content=content,
                author=author,
                published_at=published_at,
                language=language[:10] if language else None,
                media_type="article",
            ))

        return items

    def _fetch_fulltext(self, url: str) -> str | None:
        """Fetch full article text: trafilatura > Jina > readability."""
        # 1. Try trafilatura (best accuracy, fast)
        traf_result = self._fetch_via_trafilatura(url)
        if traf_result:
            return traf_result
        # 2. Try Jina Reader API (handles JS-rendered sites)
        jina_result = self._fetch_via_jina(url)
        if jina_result:
            return jina_result
        # 3. Fallback: readability (static HTML extraction)
        return self._fetch_via_readability(url)

    def _fetch_via_trafilatura(self, url: str) -> str | None:
        """Fetch full text via trafilatura (best F1 score for article extraction)."""
        try:
            resp = self.fetch(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            })
            resp.raise_for_status()
            text = trafilatura.extract(resp.text, include_comments=False, include_tables=False, favor_precision=True)
            if text and len(text) >= 200:
                return text
            logger.debug(f"Trafilatura result too short ({len(text or '')} chars) for {url}")
        except Exception as e:
            logger.debug(f"Trafilatura fetch failed for {url}: {e}")
        return None

    def _fetch_via_jina(self, url: str) -> str | None:
        """Fetch full text via Jina Reader API (handles JS rendering)."""
        try:
            from mine.config import settings
            headers = {"Accept": "text/markdown"}
            if settings.jina_api_key:
                headers["Authorization"] = f"Bearer {settings.jina_api_key}"
            resp = self.fetch(
                f"https://r.jina.ai/{url}",
                timeout=60,
                headers=headers,
            )
            resp.raise_for_status()
            text = resp.text.strip()
            if len(text) >= MIN_FULLTEXT_LEN:
                return text
            logger.debug(f"Jina result too short ({len(text)} chars) for {url}")
        except Exception as e:
            logger.debug(f"Jina fetch failed for {url}: {e}")
        return None

    def _fetch_via_readability(self, url: str) -> str | None:
        """Fetch full text via readability-lxml (static HTML only)."""
        try:
            resp = self.fetch(url, timeout=FETCH_TIMEOUT, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            })
            resp.raise_for_status()
            doc = Document(resp.text)
            html = _clean_html(doc.summary())
            plain = re.sub(r"<[^>]+>", " ", html)
            plain = re.sub(r"\s+", " ", plain).strip()
            return html if len(plain) >= MIN_FULLTEXT_LEN else None
        except Exception as e:
            logger.debug(f"Readability fetch failed for {url}: {e}")
            return None

    def _extract_content(self, entry) -> str:
        content = ""
        if "content" in entry and entry.content:
            content = entry.content[0].get("value", "")
        elif "summary" in entry:
            content = entry.get("summary", "")
        elif "description" in entry:
            content = entry.get("description", "")

        return _clean_html(content)

    def _parse_date(self, entry) -> str | None:
        for key in ("published", "updated", "created"):
            raw = entry.get(key)
            if raw:
                try:
                    dt = parsedate_to_datetime(raw)
                    return dt.isoformat()
                except Exception:
                    pass
            parsed = entry.get(f"{key}_parsed")
            if parsed:
                try:
                    dt = datetime(*parsed[:6], tzinfo=timezone.utc)
                    return dt.isoformat()
                except Exception:
                    pass
        return None
