"""Client for calling Mine REST API."""
import httpx

from studio.config import settings


class MineClient:
    def __init__(self):
        self.base_url = settings.mine_api_url

    async def get_articles(self, **params) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self.base_url}/articles", params=params)
            resp.raise_for_status()
            return resp.json()

    async def get_article(self, article_id: str) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self.base_url}/articles/{article_id}")
            resp.raise_for_status()
            return resp.json()

    async def batch_articles(self, ids: list[str]) -> list[dict]:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{self.base_url}/articles/batch", json={"ids": ids})
            resp.raise_for_status()
            return resp.json()

    async def get_hot(self, limit: int = 20, hours: int = 24) -> list[dict]:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self.base_url}/hot", params={"limit": limit, "hours": hours})
            resp.raise_for_status()
            return resp.json()

    async def get_sources(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self.base_url}/sources")
            resp.raise_for_status()
            return resp.json()

    async def get_daily_stats(self, days: int = 30) -> list[dict]:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self.base_url}/stats/daily", params={"days": days})
            resp.raise_for_status()
            return resp.json()

    async def get_stats(self) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self.base_url}/stats")
            resp.raise_for_status()
            return resp.json()


mine_client = MineClient()
