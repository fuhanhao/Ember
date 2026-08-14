"""YouTube crawler.

Two modes:
  - channel: fetch a channel's latest videos via RSSHub (primary) or the
    public YouTube RSS feed (fallback). No API key required.
  - search:  YouTube Data API v3 search for recent AI videos, then enrich
    with video statistics. Requires YOUTUBE_API_KEY.
"""
import logging
import re
from datetime import datetime, timedelta, timezone

import feedparser

from mine.config import settings
from mine.crawlers.base import BaseCrawler, CrawledItem

logger = logging.getLogger(__name__)

YT_DIRECT_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
YT_API_SEARCH = "https://www.googleapis.com/youtube/v3/search"
YT_API_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"


def _rsshub_base() -> str:
    return settings.rsshub_base_url.rstrip("/")


def _rsshub_key() -> str:
    return settings.rsshub_access_key


def _extract_video_id(entry, link: str) -> str:
    """Best-effort extraction of a YouTube video id."""
    m = re.search(r"v=([\w-]{6,})", link)
    if m:
        return m.group(1)
    m = re.search(r"youtu\.be/([\w-]{6,})", link)
    if m:
        return m.group(1)
    guid = entry.get("guid", "") or ""
    m = re.search(r"([\w-]{11})$", guid)
    if m:
        return m.group(1)
    # RSSHub description often embeds youtube-nocookie.com/embed/<id>
    desc = entry.get("description", "") or ""
    m = re.search(r"(?:embed/|/v/)([\w-]{6,})", desc)
    if m:
        return m.group(1)
    return ""


def _extract_thumbnail(entry) -> str | None:
    # RSSHub exposes thumbnail via <enclosure>
    for enc in entry.get("enclosures", []) or []:
        url = enc.get("url") or enc.get("href")
        if url and ("ytimg" in url or url.startswith("http")):
            return url
    # Direct Atom feed exposes media:thumbnail
    thumbnails = entry.get("media_thumbnail") or []
    if thumbnails and thumbnails[0].get("url"):
        return thumbnails[0]["url"]
    return None


class YoutubeCrawler(BaseCrawler):
    def crawl(self) -> list[CrawledItem]:
        mode = self.config.get("mode", "channel")
        if mode == "channel":
            return self._crawl_channels()
        if mode == "search":
            return self._crawl_search()
        logger.warning(f"Unknown youtube mode: {mode}")
        return []

    # ------------------------------------------------------------------
    # Mode 1: channel updates via RSS (RSSHub primary, direct feed fallback)
    # ------------------------------------------------------------------
    def _crawl_channels(self) -> list[CrawledItem]:
        channels = self.config.get("channels", [])
        max_items = int(self.config.get("max_items", 15))
        items: list[CrawledItem] = []

        for ch in channels:
            if isinstance(ch, dict):
                channel_id = ch.get("channel_id") or ch.get("id") or ""
                label = ch.get("name", "")
            else:
                channel_id = str(ch)
                label = ""
            if not channel_id:
                continue

            feed = self._fetch_feed(channel_id)
            if not feed:
                continue

            channel_name = (label or feed.feed.get("title", "") or channel_id)
            channel_name = re.sub(r"\s*-\s*YouTube\s*$", "", channel_name).strip()

            for entry in feed.entries[:max_items]:
                title = (entry.get("title", "") or "").strip()
                link = entry.get("link", "")
                if not title or not link:
                    continue

                video_id = _extract_video_id(entry, link)
                published_at = None
                if entry.get("published_parsed"):
                    try:
                        published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
                    except Exception:
                        pass

                content = self._entry_description(entry)
                is_live = "LIVE" in title.upper() or "直播" in title

                items.append(CrawledItem(
                    url=link,
                    title=title,
                    content=content,
                    author=channel_name,
                    published_at=published_at,
                    language=self.config.get("language", "en"),
                    media_type="video",
                    raw_metadata={
                        "video_id": video_id,
                        "channel_id": channel_id,
                        "channel_name": channel_name,
                        "thumbnail": _extract_thumbnail(entry),
                        "is_live": is_live,
                        "stats_enriched": False,
                    },
                ))

        logger.info(f"YouTube channels crawled: {len(items)} videos from {len(channels)} channels")
        return items

    def _fetch_feed(self, channel_id: str):
        """Try RSSHub first, then the direct YouTube feed."""
        attempts = []
        try:
            rsshub_url = f"{_rsshub_base()}/youtube/channel/{channel_id}"
            resp = self.fetch(
                rsshub_url,
                params={"key": _rsshub_key()} if _rsshub_key() else None,
                timeout=30,
            )
            if resp.ok and "youtube" in resp.text.lower():
                attempts.append(("rsshub", resp))
        except Exception as e:
            logger.debug(f"RSSHub YouTube fetch failed for {channel_id}: {e}")

        if not attempts:
            try:
                resp = self.fetch(YT_DIRECT_FEED.format(channel_id), timeout=20)
                if resp.ok:
                    attempts.append(("direct", resp))
            except Exception as e:
                logger.debug(f"Direct YouTube feed failed for {channel_id}: {e}")

        if not attempts:
            logger.error(f"All YouTube feed sources failed for channel {channel_id}")
            return None

        source, resp = attempts[0]
        feed = feedparser.parse(resp.content)
        if feed.bozo and not feed.entries:
            logger.error(f"Failed to parse YouTube feed for {channel_id} via {source}: {feed.bozo_exception}")
            return None
        return feed

    def _entry_description(self, entry) -> str:
        desc = entry.get("description", "") or ""
        # RSSHub embeds an iframe; keep a plain-text hint instead
        desc = re.sub(r"<iframe.*?</iframe>", "", desc, flags=re.DOTALL | re.IGNORECASE)
        desc = re.sub(r"<[^>]+>", " ", desc)
        desc = re.sub(r"\s+", " ", desc).strip()
        return desc[:500]

    # ------------------------------------------------------------------
    # Mode 2: YouTube Data API v3 search + statistics (requires API key)
    # ------------------------------------------------------------------
    def _crawl_search(self) -> list[CrawledItem]:
        api_key = self.config.get("api_key", "") or settings.youtube_api_key
        if not api_key:
            logger.warning("YOUTUBE_API_KEY not configured; skipping YouTube search mode")
            return []

        query = self.config.get("query", "AI")
        region = self.config.get("region_code", "US")
        max_results = int(self.config.get("max_results", 20))
        published_after = self.config.get("published_after_hours", 24)

        after = (datetime.now(timezone.utc) - timedelta(hours=published_after)).isoformat()

        try:
            resp = self.fetch(
                YT_API_SEARCH,
                params={
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "order": "relevance",
                    "maxResults": max_results,
                    "regionCode": region,
                    "publishedAfter": after,
                    "key": api_key,
                },
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"YouTube search failed: {e}")
            return []

        videos = data.get("items", [])
        stats_map = self._fetch_statistics(api_key, [v["id"]["videoId"] for v in videos])

        items = []
        for v in videos:
            snippet = v.get("snippet", {})
            video_id = v.get("id", {}).get("videoId", "")
            title = snippet.get("title", "")
            if not video_id or not title:
                continue

            stat = stats_map.get(video_id, {})
            items.append(CrawledItem(
                url=f"https://www.youtube.com/watch?v={video_id}",
                title=title,
                content=(snippet.get("description", "") or "")[:500],
                author=snippet.get("channelTitle"),
                published_at=snippet.get("publishedAt"),
                language=self.config.get("language", "en"),
                media_type="video",
                raw_metadata={
                    "video_id": video_id,
                    "channel_id": snippet.get("channelId"),
                    "channel_name": snippet.get("channelTitle"),
                    "thumbnail": (snippet.get("thumbnails") or {}).get("high", {}).get("url"),
                    "views": stat.get("viewCount"),
                    "likes": stat.get("likeCount"),
                    "comments": stat.get("commentCount"),
                    "query": query,
                    "stats_enriched": bool(stat),
                },
            ))

        logger.info(f"YouTube search '{query}' returned {len(items)} videos")
        return items

    def _fetch_statistics(self, api_key: str, video_ids: list[str]) -> dict:
        """Batch fetch view/like counts for video ids (max 50 per call)."""
        if not video_ids:
            return {}
        stats_map: dict[str, dict] = {}
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i + 50]
            try:
                resp = self.fetch(
                    YT_API_VIDEOS,
                    params={
                        "part": "statistics",
                        "id": ",".join(batch),
                        "key": api_key,
                    },
                    timeout=20,
                )
                resp.raise_for_status()
                for item in resp.json().get("items", []):
                    stats_map[item["id"]] = {
                        k: int(v) if str(v).isdigit() else v
                        for k, v in (item.get("statistics") or {}).items()
                    }
            except Exception as e:
                logger.error(f"YouTube statistics fetch failed for batch {i}: {e}")
        return stats_map
