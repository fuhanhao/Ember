import logging
from datetime import datetime, timezone

from mine.crawlers.base import BaseCrawler, CrawledItem

logger = logging.getLogger(__name__)

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_NEW_URL = "https://hacker-news.firebaseio.com/v0/newstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"


class HnApiCrawler(BaseCrawler):
    def crawl(self) -> list[CrawledItem]:
        max_items = self.config.get("max_items", 30)
        story_type = self.config.get("story_type", "top")  # top or new

        url = HN_TOP_URL if story_type == "top" else HN_NEW_URL
        try:
            resp = self.fetch(url, timeout=15)
            resp.raise_for_status()
            story_ids = resp.json()[:max_items]
        except Exception as e:
            logger.error(f"Failed to fetch HN story list: {e}")
            return []

        items = []
        for sid in story_ids:
            try:
                resp = self.fetch(HN_ITEM_URL.format(sid), timeout=10)
                resp.raise_for_status()
                story = resp.json()
            except Exception:
                continue

            if not story or story.get("type") != "story":
                continue

            title = story.get("title", "")
            url = story.get("url", f"https://news.ycombinator.com/item?id={sid}")
            if not title:
                continue

            published_at = None
            if story.get("time"):
                published_at = datetime.fromtimestamp(story["time"], tz=timezone.utc).isoformat()

            text = story.get("text", "")
            score = story.get("score", 0)
            descendants = story.get("descendants", 0)

            items.append(CrawledItem(
                url=url,
                title=title,
                content=text or f"HN Score: {score}, Comments: {descendants}",
                author=story.get("by"),
                published_at=published_at,
                language="en",
                media_type="discussion",
                raw_metadata={"hn_id": sid, "score": score, "comments": descendants},
            ))

        return items
