"""Twitter/X crawler via Apify actor (pay-per-result or CU-only)."""
import logging
import time
from datetime import datetime, timezone

import requests
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from mine.config import settings
from mine.crawlers.base import BaseCrawler, CrawledItem
from mine.models import ApifyKey

logger = logging.getLogger(__name__)

APIFY_BASE = "https://api.apify.com/v2"
# Default actor: a]fast, cheap Twitter scraper
DEFAULT_ACTOR_ID = "danek~twitter-scraper-ppr"
POLL_INTERVAL = 5  # seconds between status checks
MAX_WAIT = 120  # max seconds to wait for actor run


def _pick_api_key() -> str | None:
    """Round-robin pick an active, healthy Apify API key from the pool."""
    engine = create_engine(settings.database_url_sync)
    with Session(engine) as session:
        # Pick the key with the oldest last_used_at (round-robin)
        key_row = session.execute(
            select(ApifyKey)
            .where(ApifyKey.is_active.is_(True))
            .where(ApifyKey.status.in_(["healthy", "untested"]))
            .order_by(ApifyKey.last_used_at.asc().nullsfirst())
            .limit(1)
        ).scalar_one_or_none()

        if not key_row:
            return None

        key_row.last_used_at = datetime.now(timezone.utc)
        session.commit()
        api_key = key_row.api_key
    engine.dispose()
    return api_key


class ApifyTwitterCrawler(BaseCrawler):
    """Crawl a Twitter user's timeline via Apify."""

    def crawl(self) -> list[CrawledItem]:
        handle = self.config.get("handle", "")
        if not handle:
            logger.warning(f"No Twitter handle configured for {self.source_id}")
            return []

        api_token = _pick_api_key()
        if not api_token:
            logger.error(f"No available Apify API key for {self.source_id}")
            return []

        actor_id = self.config.get("actor_id", DEFAULT_ACTOR_ID)
        max_tweets = self.config.get("max_tweets", 10)

        # Build actor input (danek/twitter-scraper-ppr schema)
        actor_input = {
            "username": handle,
            "max_posts": max_tweets,
        }

        try:
            # Start actor run
            run_url = f"{APIFY_BASE}/acts/{actor_id}/runs"
            resp = requests.post(
                run_url,
                params={"token": api_token},
                json=actor_input,
                timeout=30,
            )
            resp.raise_for_status()
            run_data = resp.json().get("data", {})
            run_id = run_data.get("id")
            if not run_id:
                logger.error(f"Apify actor start failed for {self.source_id}: no run ID")
                return []

            logger.info(f"Apify run started for {self.source_id}: {run_id}")

            # Poll for completion
            status_url = f"{APIFY_BASE}/actor-runs/{run_id}"
            elapsed = 0
            while elapsed < MAX_WAIT:
                time.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL
                status_resp = requests.get(
                    status_url,
                    params={"token": api_token},
                    timeout=15,
                )
                status_resp.raise_for_status()
                status = status_resp.json().get("data", {}).get("status")
                if status == "SUCCEEDED":
                    break
                if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                    logger.error(f"Apify run {run_id} ended with status: {status}")
                    return []

            if elapsed >= MAX_WAIT:
                logger.error(f"Apify run {run_id} timed out after {MAX_WAIT}s")
                return []

            # Fetch dataset items
            dataset_id = status_resp.json().get("data", {}).get("defaultDatasetId")
            if not dataset_id:
                logger.error(f"No dataset for Apify run {run_id}")
                return []

            items_url = f"{APIFY_BASE}/datasets/{dataset_id}/items"
            items_resp = requests.get(
                items_url,
                params={"token": api_token, "format": "json"},
                timeout=30,
            )
            items_resp.raise_for_status()
            raw_items = items_resp.json()

            return self._parse_tweets(raw_items, handle)

        except Exception as e:
            logger.error(f"Apify crawl failed for {self.source_id}: {e}")
            return []

    def _parse_tweets(self, raw_items: list[dict], handle: str) -> list[CrawledItem]:
        """Parse Apify tweet results into CrawledItem list."""
        items = []
        for tweet in raw_items:
            tweet_id = tweet.get("tweet_id") or tweet.get("id") or tweet.get("tweetId") or tweet.get("id_str", "")
            text = tweet.get("text") or tweet.get("full_text") or tweet.get("tweetText", "")
            if not tweet_id or not text:
                continue

            url = tweet.get("url") or f"https://x.com/{handle}/status/{tweet_id}"

            # Parse created_at
            published_at = None
            raw_date = tweet.get("created_at") or tweet.get("createdAt") or tweet.get("timestamp")
            if raw_date:
                published_at = self._parse_date(raw_date)

            author_data = tweet.get("author")
            if isinstance(author_data, dict):
                author = author_data.get("screen_name") or author_data.get("userName") or handle
            else:
                author = handle

            is_rt = text.startswith("RT @")

            items.append(CrawledItem(
                url=url,
                title=text[:120].strip(),
                content=text,
                author=f"@{author}",
                published_at=published_at,
                language=tweet.get("lang", "en"),
                media_type="tweet",
                raw_metadata={
                    "tweet_id": str(tweet_id),
                    "handle": handle,
                    "retweet_count": tweet.get("retweets") or tweet.get("retweetCount") or tweet.get("retweet_count", 0),
                    "like_count": tweet.get("favorites") or tweet.get("likeCount") or tweet.get("favorite_count", 0),
                    "reply_count": tweet.get("replies") or tweet.get("replyCount") or tweet.get("reply_count", 0),
                    "views": tweet.get("views", 0),
                    "is_retweet": is_rt,
                },
            ))

        logger.info(f"Parsed {len(items)} tweets for @{handle}")
        return items

    def _parse_date(self, raw: str) -> str | None:
        for fmt in (
            "%a %b %d %H:%M:%S %z %Y",  # Twitter classic format
            "%Y-%m-%dT%H:%M:%S.%fZ",     # ISO format
            "%Y-%m-%dT%H:%M:%SZ",
        ):
            try:
                return datetime.strptime(raw, fmt).isoformat()
            except (ValueError, TypeError):
                continue
        return raw if isinstance(raw, str) else None
