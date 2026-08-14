"""Twitter/X crawler via twitterapi.io (the same provider used by the
user's n8n aggregator workflow).

Two modes:
  - last_tweets:     fetch latest tweets from a list of user handles
  - advanced_search: search recent tweets by keyword

Requires TWITTERAPI_IO_KEY.
"""
import logging
from datetime import datetime, timezone

from mine.config import settings
from mine.crawlers.base import BaseCrawler, CrawledItem

logger = logging.getLogger(__name__)

TWITTERAPI_IO_BASE = "https://api.twitterapi.io/twitter"


class TwitterApiIoCrawler(BaseCrawler):
    def crawl(self) -> list[CrawledItem]:
        api_key = self.config.get("api_key", "") or settings.twitterapi_io_key
        if not api_key:
            logger.warning(f"TWITTERAPI_IO_KEY not configured; skipping {self.source_id}")
            return []

        mode = self.config.get("mode", "last_tweets")
        headers = {"X-API-Key": api_key}

        if mode == "advanced_search":
            return self._advanced_search(headers)
        return self._last_tweets(headers)

    def _last_tweets(self, headers: dict) -> list[CrawledItem]:
        handles = self.config.get("handles", [])
        max_tweets = int(self.config.get("max_tweets", 10))
        items: list[CrawledItem] = []

        for handle in handles:
            handle = str(handle).lstrip("@")
            if not handle:
                continue
            try:
                resp = self.fetch(
                    f"{TWITTERAPI_IO_BASE}/user/last_tweets",
                    headers=headers,
                    params={"userName": handle, "count": max_tweets},
                    timeout=30,
                )
                resp.raise_for_status()
                tweets = self._extract_tweets(resp.json())
            except Exception as e:
                logger.error(f"twitterapi.io last_tweets failed for @{handle}: {e}")
                continue

            parsed = self._parse_tweets(tweets, handle)
            items.extend(parsed)
            logger.info(f"twitterapi.io @{handle}: {len(parsed)} tweets")

        return items

    def _advanced_search(self, headers: dict) -> list[CrawledItem]:
        query = self.config.get("query", "AI")
        query_type = self.config.get("query_type", "Top")
        max_tweets = int(self.config.get("max_tweets", 20))
        try:
            resp = self.fetch(
                f"{TWITTERAPI_IO_BASE}/tweet/advanced_search",
                headers=headers,
                params={
                    "query": query,
                    "queryType": query_type,
                    "count": max_tweets,
                },
                timeout=30,
            )
            resp.raise_for_status()
            tweets = self._extract_tweets(resp.json())
        except Exception as e:
            logger.error(f"twitterapi.io advanced_search failed: {e}")
            return []

        items = self._parse_tweets(tweets, None)
        logger.info(f"twitterapi.io search '{query}': {len(items)} tweets")
        return items

    @staticmethod
    def _extract_tweets(payload: dict) -> list[dict]:
        if not isinstance(payload, dict):
            return []
        data = payload.get("data")
        if isinstance(data, dict):
            data = data.get("tweets") or data.get("items") or []
        if not isinstance(data, list):
            data = payload.get("tweets") or []
        return [t for t in data if isinstance(t, dict)]

    def _parse_tweets(self, tweets: list[dict], default_handle: str | None) -> list[CrawledItem]:
        items: list[CrawledItem] = []
        for tw in tweets:
            text = tw.get("text") or tw.get("content") or tw.get("fullText") or ""
            tweet_id = tw.get("id") or tw.get("tweet_id") or tw.get("id_str") or ""
            if not text or not tweet_id:
                continue

            user = tw.get("user") or tw.get("author") or {}
            handle = user.get("userName") or user.get("screen_name") or user.get("username") or default_handle
            handle = str(handle).lstrip("@") if handle else default_handle

            published_at = tw.get("createdAt") or tw.get("created_at") or tw.get("timestamp")
            if published_at:
                published_at = self._parse_date(published_at)

            url = tw.get("url") or (f"https://x.com/{handle}/status/{tweet_id}" if handle else "")

            items.append(CrawledItem(
                url=url,
                title=text[:120].strip(),
                content=text,
                author=f"@{handle}" if handle else None,
                published_at=published_at,
                language=tw.get("lang") or tw.get("language") or "en",
                media_type="tweet",
                raw_metadata={
                    "tweet_id": str(tweet_id),
                    "handle": handle,
                    "like_count": tw.get("likeCount") or tw.get("favorite_count") or tw.get("likes", 0),
                    "retweet_count": tw.get("retweetCount") or tw.get("retweet_count") or tw.get("retweets", 0),
                    "reply_count": tw.get("replyCount") or tw.get("reply_count") or tw.get("replies", 0),
                    "view_count": tw.get("viewCount") or tw.get("views", 0),
                    "is_retweet": text.startswith("RT @"),
                },
            ))
        return items

    def _parse_date(self, raw: str) -> str | None:
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%a %b %d %H:%M:%S %z %Y",
        ):
            try:
                return datetime.strptime(raw, fmt).isoformat()
            except (ValueError, TypeError):
                continue
        return raw if isinstance(raw, str) else None
