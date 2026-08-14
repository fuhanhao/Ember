import logging
from datetime import datetime

from mine.config import settings
from mine.crawlers.base import BaseCrawler, CrawledItem

logger = logging.getLogger(__name__)


class GithubApiCrawler(BaseCrawler):
    def crawl(self) -> list[CrawledItem]:
        mode = self.config.get("mode", "releases")  # releases or trending
        if mode == "releases":
            return self._crawl_releases()
        elif mode == "trending":
            return self._crawl_trending()
        return []

    def _get_headers(self) -> dict:
        headers = {"Accept": "application/vnd.github+json"}
        token = self.config.get("token", "") or settings.github_token
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _crawl_releases(self) -> list[CrawledItem]:
        repos = self.config.get("repos", [])
        items = []

        for repo in repos:
            try:
                resp = self.fetch(
                    f"https://api.github.com/repos/{repo}/releases",
                    headers=self._get_headers(),
                    params={"per_page": 5},
                    timeout=15,
                )
                resp.raise_for_status()
                releases = resp.json()
            except Exception as e:
                logger.error(f"Failed to fetch releases for {repo}: {e}")
                continue

            for rel in releases:
                tag = rel.get("tag_name", "")
                name = rel.get("name", tag)
                body = rel.get("body", "") or ""
                title = f"{repo} {name}" if name else f"{repo} {tag}"

                items.append(CrawledItem(
                    url=rel.get("html_url", f"https://github.com/{repo}"),
                    title=title,
                    content=body[:2000],
                    author=rel.get("author", {}).get("login"),
                    published_at=rel.get("published_at"),
                    language="en",
                    media_type="release",
                    raw_metadata={"repo": repo, "tag": tag, "prerelease": rel.get("prerelease", False)},
                ))

        return items

    def _crawl_trending(self) -> list[CrawledItem]:
        """Use GitHub search API to find recently created popular repos."""
        language = self.config.get("language", "")
        query = self.config.get("query", "stars:>100 created:>2026-01-01")
        if language:
            query += f" language:{language}"

        try:
            resp = self.fetch(
                "https://api.github.com/search/repositories",
                headers=self._get_headers(),
                params={"q": query, "sort": "stars", "order": "desc", "per_page": 20},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch GitHub trending: {e}")
            return []

        items = []
        for repo in data.get("items", []):
            desc = repo.get("description", "") or ""
            items.append(CrawledItem(
                url=repo.get("html_url", ""),
                title=f"{repo['full_name']} - {desc[:100]}" if desc else repo["full_name"],
                content=f"Stars: {repo.get('stargazers_count', 0)}, Forks: {repo.get('forks_count', 0)}, Language: {repo.get('language', 'N/A')}\n\n{desc}",
                author=repo.get("owner", {}).get("login"),
                published_at=repo.get("created_at"),
                language="en",
                media_type="repository",
                raw_metadata={
                    "stars": repo.get("stargazers_count", 0),
                    "forks": repo.get("forks_count", 0),
                    "language": repo.get("language"),
                    "topics": repo.get("topics", []),
                },
            ))

        return items
