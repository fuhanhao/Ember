from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import requests

from mine.utils.http_client import managed_get, managed_request


@dataclass
class CrawledItem:
    url: str
    title: str
    content: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[str] = None  # ISO format
    language: Optional[str] = None
    media_type: Optional[str] = None
    raw_metadata: dict = field(default_factory=dict)


class BaseCrawler(ABC):
    def __init__(self, source_id: str, config: dict):
        self.source_id = source_id
        self.config = config

    @abstractmethod
    def crawl(self) -> list[CrawledItem]:
        """Fetch new items from the source. Returns a list of CrawledItem."""
        ...

    def fetch(
        self,
        url: str,
        *,
        timeout: int = 15,
        headers: dict | None = None,
        use_proxy: bool | None = None,
        **kwargs,
    ) -> requests.Response:
        """Rate-limited, proxy-aware HTTP GET. All crawlers should use this."""
        return managed_get(
            url,
            timeout=timeout,
            headers=headers,
            use_proxy=use_proxy,
            **kwargs,
        )

    def fetch_request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> requests.Response:
        """Rate-limited, proxy-aware HTTP request (any method)."""
        return managed_request(method, url, **kwargs)
