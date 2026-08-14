"""Juejin (掘金) crawler via public API."""
import logging
from datetime import datetime, timezone

from mine.crawlers.base import BaseCrawler, CrawledItem

logger = logging.getLogger(__name__)

# AI category ID on juejin
DEFAULT_CATE_ID = "6809637769959178254"
API_URL = "https://api.juejin.cn/recommend_api/v1/article/recommend_cate_tag_feed"


class JuejinApiCrawler(BaseCrawler):
    def crawl(self) -> list[CrawledItem]:
        cate_id = self.config.get("cate_id", DEFAULT_CATE_ID)
        limit = self.config.get("limit", 20)

        try:
            resp = self.fetch_request(
                "POST",
                API_URL,
                json={
                    "id_type": 2,
                    "sort_type": 200,
                    "cate_id": cate_id,
                    "cursor": "0",
                    "limit": limit,
                },
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Juejin API failed for {self.source_id}: {e}")
            return []

        items = []
        for item in data.get("data", []):
            info = item.get("article_info", {})
            article_id = info.get("article_id", "")
            title = info.get("title", "").strip()
            if not article_id or not title:
                continue

            url = f"https://juejin.cn/post/{article_id}"
            content = info.get("brief_content", "")
            author_info = item.get("author_info", {})
            author = author_info.get("user_name")

            ctime = info.get("ctime", "")
            published_at = None
            if ctime:
                try:
                    published_at = datetime.fromtimestamp(
                        int(ctime), tz=timezone.utc
                    ).isoformat()
                except (ValueError, TypeError):
                    pass

            items.append(CrawledItem(
                url=url,
                title=title,
                content=content,
                author=author,
                published_at=published_at,
                language="zh",
                media_type="article",
                raw_metadata={
                    "view_count": info.get("view_count", 0),
                    "digg_count": info.get("digg_count", 0),
                    "comment_count": info.get("comment_count", 0),
                    "collect_count": info.get("collect_count", 0),
                },
            ))

        return items
