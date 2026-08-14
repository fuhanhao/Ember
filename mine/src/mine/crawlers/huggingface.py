import logging

from mine.crawlers.base import BaseCrawler, CrawledItem

logger = logging.getLogger(__name__)

HF_PAPERS_URL = "https://huggingface.co/api/daily_papers"
HF_MODELS_URL = "https://huggingface.co/api/models"


class HfApiCrawler(BaseCrawler):
    def crawl(self) -> list[CrawledItem]:
        mode = self.config.get("mode", "papers")  # papers or models
        if mode == "papers":
            return self._crawl_papers()
        elif mode == "models":
            return self._crawl_models()
        return []

    def _crawl_papers(self) -> list[CrawledItem]:
        try:
            resp = self.fetch(HF_PAPERS_URL, timeout=15)
            resp.raise_for_status()
            papers = resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch HF daily papers: {e}")
            return []

        items = []
        for paper in papers:
            p = paper.get("paper", paper)
            paper_id = p.get("id", "")
            title = p.get("title", "")
            summary = p.get("summary", "") or ""
            if not title:
                continue

            authors = p.get("authors", [])
            author_names = ", ".join(a.get("name", "") for a in authors[:5]) if authors else None

            items.append(CrawledItem(
                url=f"https://huggingface.co/papers/{paper_id}" if paper_id else "",
                title=title,
                content=summary[:2000],
                author=author_names,
                published_at=p.get("publishedAt") or paper.get("publishedAt"),
                language="en",
                media_type="paper",
                raw_metadata={"paper_id": paper_id, "upvotes": paper.get("paper", {}).get("upvotes", 0) if isinstance(paper.get("paper"), dict) else 0},
            ))

        return items

    def _crawl_models(self) -> list[CrawledItem]:
        try:
            resp = self.fetch(
                HF_MODELS_URL,
                params={"sort": "trendingScore", "direction": "-1", "limit": 20},
                timeout=15,
            )
            resp.raise_for_status()
            models = resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch HF trending models: {e}")
            return []

        items = []
        for model in models:
            model_id = model.get("modelId", model.get("id", ""))
            if not model_id:
                continue

            items.append(CrawledItem(
                url=f"https://huggingface.co/{model_id}",
                title=f"Trending Model: {model_id}",
                content=f"Pipeline: {model.get('pipeline_tag', 'N/A')}, Downloads: {model.get('downloads', 0)}, Likes: {model.get('likes', 0)}",
                author=model_id.split("/")[0] if "/" in model_id else None,
                published_at=model.get("createdAt"),
                language="en",
                media_type="model",
                raw_metadata={
                    "pipeline_tag": model.get("pipeline_tag"),
                    "downloads": model.get("downloads", 0),
                    "likes": model.get("likes", 0),
                    "tags": model.get("tags", []),
                },
            ))

        return items
