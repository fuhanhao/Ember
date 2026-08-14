"""Shared HTTP client with per-domain rate limiting and proxy rotation.

Rate limiter: Redis sliding-window counter per domain.
Proxy pool:   Supports 3 modes — static list, tunnel, and API-extract with auto-refresh.
"""

import logging
import random
import time
from urllib.parse import urlparse

import redis
import requests

from mine.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis connection (lazy singleton)
# ---------------------------------------------------------------------------
_redis: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


# ---------------------------------------------------------------------------
# Per-domain rate limiter  (sliding window counter in Redis)
# ---------------------------------------------------------------------------
class RateLimiter:
    """Allow at most `max_requests` per `window_seconds` for each domain."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def _key(self, domain: str) -> str:
        return f"mine:ratelimit:{domain}"

    def wait_if_needed(self, url: str) -> None:
        """Block until the request is allowed under the rate limit."""
        domain = urlparse(url).netloc
        if not domain:
            return

        r = _get_redis()
        key = self._key(domain)
        now = time.time()
        window_start = now - self.window_seconds

        pipe = r.pipeline()
        pipe.zremrangebyscore(key, "-inf", window_start)
        pipe.zcard(key)
        _, count = pipe.execute()

        if count >= self.max_requests:
            oldest = r.zrange(key, 0, 0, withscores=True)
            if oldest:
                wait = oldest[0][1] + self.window_seconds - now
                if wait > 0:
                    logger.debug(f"Rate limit hit for {domain}, sleeping {wait:.1f}s")
                    time.sleep(min(wait, 30.0))

        r.zadd(key, {f"{now}:{random.randint(0, 99999)}": now})
        r.expire(key, self.window_seconds * 2)


# ---------------------------------------------------------------------------
# Proxy pool — supports static list, tunnel, and API-extract
# ---------------------------------------------------------------------------
class ProxyPool:
    """Proxy rotation with health tracking and auto-refresh.

    Configuration via settings:
      - proxy_urls:              Static list or tunnel address (comma-separated)
      - proxy_api_url:           API endpoint that returns fresh IPs
      - proxy_api_refresh_seconds: How often to call the API
      - proxy_api_protocol:      Protocol prefix for extracted IPs (http/socks5)

    Modes (auto-detected):
      1. API extract  — proxy_api_url is set → periodically fetch IPs from vendor API
      2. Static/Tunnel — proxy_urls is set   → use directly, round-robin
      3. Disabled      — neither set         → all requests go direct
    """

    def __init__(self):
        self._static: list[str] = []
        self._api_proxies: list[str] = []
        self._dead: set[str] = set()
        self._index = 0
        self._last_api_fetch: float = 0.0

        raw = settings.proxy_urls.strip()
        if raw:
            self._static = [p.strip() for p in raw.split(",") if p.strip()]

    @property
    def mode(self) -> str:
        if settings.proxy_api_url:
            return "api"
        if self._static:
            return "static"
        return "disabled"

    @property
    def enabled(self) -> bool:
        return self.mode != "disabled"

    def _refresh_api_proxies(self) -> None:
        """Call vendor API to get a fresh batch of proxy IPs."""
        now = time.time()
        if now - self._last_api_fetch < settings.proxy_api_refresh_seconds:
            return
        self._last_api_fetch = now

        try:
            resp = requests.get(settings.proxy_api_url, timeout=10)
            resp.raise_for_status()
            data = resp.json() if "json" in resp.headers.get("content-type", "") else None

            ips: list[str] = []
            if data:
                # Common vendor formats
                if isinstance(data, list):
                    ips = data
                elif isinstance(data, dict):
                    # 快代理 format: {"code": 0, "data": {"proxy_list": ["ip:port", ...]}}
                    proxy_list = data.get("data", {}).get("proxy_list", [])
                    if proxy_list:
                        ips = proxy_list
                    # 芝麻代理 format: {"code": 0, "data": [{"ip": "x", "port": 1234}]}
                    items = data.get("data", [])
                    if isinstance(items, list) and items and isinstance(items[0], dict):
                        ips = [f"{d['ip']}:{d['port']}" for d in items if "ip" in d]
                    # Simple format: {"proxies": ["ip:port"]}
                    if not ips:
                        ips = data.get("proxies", [])
            else:
                # Plain text: one ip:port per line
                ips = [line.strip() for line in resp.text.strip().splitlines() if line.strip()]

            proto = settings.proxy_api_protocol
            self._api_proxies = [f"{proto}://{ip}" if "://" not in ip else ip for ip in ips]
            self._dead.clear()
            logger.info(f"Proxy API refreshed: {len(self._api_proxies)} IPs loaded")

        except Exception as e:
            logger.error(f"Failed to refresh proxy API: {e}")

    def _alive(self) -> list[str]:
        pool = self._api_proxies if self.mode == "api" else self._static
        return [p for p in pool if p not in self._dead]

    def next(self) -> dict | None:
        """Return a requests-compatible proxies dict, or None (direct)."""
        if self.mode == "api":
            self._refresh_api_proxies()

        alive = self._alive()
        if not alive:
            if self.mode == "api":
                # Force refresh if all dead
                self._last_api_fetch = 0
                self._refresh_api_proxies()
                alive = self._alive()
            if not alive:
                return None

        proxy = alive[self._index % len(alive)]
        self._index += 1
        return {"http": proxy, "https": proxy}

    def mark_dead(self, proxies: dict | None) -> None:
        if not proxies:
            return
        url = proxies.get("http", "")
        if url:
            self._dead.add(url)
            logger.warning(f"Proxy marked dead: {url} ({len(self._dead)} dead)")

    def mark_alive(self, proxies: dict | None) -> None:
        if not proxies:
            return
        url = proxies.get("http", "")
        self._dead.discard(url)

    def reset_dead(self) -> None:
        self._dead.clear()

    def stats(self) -> dict:
        pool = self._api_proxies if self.mode == "api" else self._static
        return {
            "mode": self.mode,
            "total": len(pool),
            "alive": len(self._alive()),
            "dead": len(self._dead),
        }


# ---------------------------------------------------------------------------
# Managed HTTP client
# ---------------------------------------------------------------------------
_rate_limiter: RateLimiter | None = None
_proxy_pool: ProxyPool | None = None


def _get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            max_requests=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window,
        )
    return _rate_limiter


def _get_proxy_pool() -> ProxyPool:
    global _proxy_pool
    if _proxy_pool is None:
        _proxy_pool = ProxyPool()
    return _proxy_pool


def get_proxy_pool() -> ProxyPool:
    """Public accessor for proxy pool (e.g. for stats endpoint)."""
    return _get_proxy_pool()


# Per-domain override: domain -> (max_req, window_sec)
DOMAIN_LIMITS: dict[str, tuple[int, int]] = {
    "api.github.com": (10, 60),
    "hacker-news.firebaseio.com": (30, 60),
    "huggingface.co": (10, 60),
    "www.googleapis.com": (5, 60),
    "www.youtube.com": (10, 60),
    "rsshub": (30, 60),
    "api.twitterapi.io": (5, 60),
    "sspai.com": (3, 60),
    "juejin.cn": (3, 60),
    "r.jina.ai": (5, 60),
}


def managed_request(
    method: str,
    url: str,
    *,
    timeout: int = 15,
    use_proxy: bool | None = None,
    max_retries: int = 2,
    headers: dict | None = None,
    **kwargs,
) -> requests.Response:
    """Rate-limited, proxy-aware HTTP request.

    Args:
        method: HTTP method (get, post, etc.)
        url: Target URL.
        timeout: Request timeout in seconds.
        use_proxy: Force proxy on/off. None = auto (use proxy if pool is configured).
        max_retries: Retry count on transient failures (5xx, timeout, proxy error).
        headers: Additional headers.
        **kwargs: Passed through to requests.request().

    Returns:
        requests.Response

    Raises:
        requests.RequestException on final failure.
    """
    limiter = _get_rate_limiter()
    pool = _get_proxy_pool()

    domain = urlparse(url).netloc
    if domain in DOMAIN_LIMITS:
        max_req, window = DOMAIN_LIMITS[domain]
        domain_limiter = RateLimiter(max_req, window)
        domain_limiter.wait_if_needed(url)
    else:
        limiter.wait_if_needed(url)

    should_proxy = pool.enabled if use_proxy is None else use_proxy
    last_exc = None

    for attempt in range(max_retries + 1):
        proxies = pool.next() if should_proxy else None

        try:
            resp = requests.request(
                method,
                url,
                timeout=timeout,
                headers=headers,
                proxies=proxies,
                **kwargs,
            )
            if proxies:
                pool.mark_alive(proxies)

            if resp.status_code >= 500 and attempt < max_retries:
                wait = 2 ** attempt
                logger.warning(f"{url} returned {resp.status_code}, retry in {wait}s")
                time.sleep(wait)
                continue

            return resp

        except (requests.ConnectionError, requests.Timeout) as e:
            last_exc = e
            if proxies:
                pool.mark_dead(proxies)
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.warning(
                    f"Request failed ({e.__class__.__name__}), "
                    f"retry {attempt + 1}/{max_retries} in {wait}s"
                )
                time.sleep(wait)
            continue

    raise last_exc or requests.RequestException(f"All {max_retries + 1} attempts failed for {url}")


def managed_get(url: str, **kwargs) -> requests.Response:
    """Shortcut for managed_request('GET', ...)."""
    return managed_request("GET", url, **kwargs)
