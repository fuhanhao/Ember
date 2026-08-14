import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from mine.crawlers.base import BaseCrawler, CrawledItem


class PodcastRssCrawler(BaseCrawler):
    def crawl(self) -> list[CrawledItem]:
        feed_url = self.config.get("feed_url", "")
        if not feed_url:
            return []

        feed = feedparser.parse(feed_url)
        show_name = feed.feed.get("title", "")
        items = []

        for entry in feed.entries:
            url = entry.get("link", "")
            title = entry.get("title", "")
            if not url or not title:
                continue

            # Extract audio enclosure
            audio_url = None
            duration = None
            for enc in entry.get("enclosures", []):
                if enc.get("type", "").startswith("audio/"):
                    audio_url = enc.get("href")
                    break
            # itunes duration
            duration = entry.get("itunes_duration", "")

            # Description
            content = ""
            if "summary" in entry:
                content = re.sub(r"<[^>]+>", " ", entry.get("summary", ""))
                content = re.sub(r"\s+", " ", content).strip()

            published_at = self._parse_date(entry)
            language = feed.feed.get("language", "en")

            items.append(CrawledItem(
                url=url,
                title=f"[{show_name}] {title}" if show_name else title,
                content=content,
                author=entry.get("author") or feed.feed.get("author"),
                published_at=published_at,
                language=language[:10] if language else None,
                media_type="podcast",
                raw_metadata={
                    "show": show_name,
                    "audio_url": audio_url,
                    "duration": duration,
                },
            ))

        return items

    def _parse_date(self, entry) -> str | None:
        for key in ("published", "updated"):
            raw = entry.get(key)
            if raw:
                try:
                    return parsedate_to_datetime(raw).isoformat()
                except Exception:
                    pass
            parsed = entry.get(f"{key}_parsed")
            if parsed:
                try:
                    return datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()
                except Exception:
                    pass
        return None
