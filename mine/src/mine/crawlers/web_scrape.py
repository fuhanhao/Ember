import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from mine.crawlers.base import BaseCrawler, CrawledItem

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]


class WebScrapeCrawler(BaseCrawler):
    """Lightweight web scraper using requests + regex extraction.
    For sites that don't need JS rendering. Falls back gracefully.
    """

    def crawl(self) -> list[CrawledItem]:
        target_url = self.config.get("url", "")
        if not target_url:
            return []

        selectors = self.config.get("selectors", {})
        # selectors example:
        # {
        #   "article_pattern": "<article.*?>(.*?)</article>",
        #   "title_pattern": "<h[123].*?>(.*?)</h[123]>",
        #   "link_pattern": "<a\\s+href=\"(.*?)\"",
        #   "content_pattern": "<p.*?>(.*?)</p>"
        # }

        headers = {
            "User-Agent": USER_AGENTS[hash(self.source_id) % len(USER_AGENTS)],
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        try:
            resp = self.fetch(target_url, headers=headers, timeout=20)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            html = resp.text
        except Exception as e:
            logger.error(f"Web scrape failed for {self.source_id} ({target_url}): {e}")
            return []

        return self._extract_items(html, target_url, selectors)

    def _extract_items(self, html: str, base_url: str, selectors: dict) -> list[CrawledItem]:
        items = []

        # Try article blocks first
        article_pattern = selectors.get("article_pattern", r'<article[^>]*>(.*?)</article>')
        blocks = re.findall(article_pattern, html, re.DOTALL | re.IGNORECASE)

        if not blocks:
            # Fallback: extract all links with titles
            blocks = [html]

        title_pattern = selectors.get("title_pattern", r'<h[1-3][^>]*>(.*?)</h[1-3]>')
        link_pattern = selectors.get("link_pattern", r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>')
        content_pattern = selectors.get("content_pattern", r'<p[^>]*>(.*?)</p>')

        seen_urls = set()

        for block in blocks:
            # Extract title
            titles = re.findall(title_pattern, block, re.DOTALL | re.IGNORECASE)
            if not titles:
                continue
            title = self._strip_html(titles[0]).strip()
            if not title or len(title) < 5:
                continue

            # Extract link
            links = re.findall(link_pattern, block, re.IGNORECASE)
            url = ""
            for link in links:
                if link.startswith(("http", "/")):
                    url = urljoin(base_url, link)
                    break
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            # Extract content snippets
            paragraphs = re.findall(content_pattern, block, re.DOTALL | re.IGNORECASE)
            content = " ".join(self._strip_html(p) for p in paragraphs[:5]).strip()

            items.append(CrawledItem(
                url=url,
                title=title,
                content=content or None,
                author=None,
                published_at=None,
                language=self.config.get("language", "zh"),
                media_type="article",
            ))

        return items[:30]  # Cap per crawl

    def _strip_html(self, text: str) -> str:
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
