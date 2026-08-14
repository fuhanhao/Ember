"""Periodic health check for Twitter/X data ingestion via RSSHub."""
import logging

import httpx
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from mine.celery_app import celery
from mine.config import settings
from mine.models import DataSource, RawArticle

logger = logging.getLogger(__name__)

RSSHUB_BASE = "http://rsshub:1200"
ACCESS_KEY = "forge_mine_2026"

# A small set of high-activity accounts to probe
PROBE_HANDLES = ["karpathy", "OpenAI", "elonmusk"]


@celery.task(name="mine.tasks.twitter_health_check")
def twitter_health_check():
    """Test RSSHub Twitter routes and report cookie health."""
    results = {"ok": 0, "fail": 0, "errors": []}

    for handle in PROBE_HANDLES:
        url = f"{RSSHUB_BASE}/twitter/user/{handle}?key={ACCESS_KEY}"
        try:
            resp = httpx.get(url, timeout=30)
            if resp.status_code == 200:
                results["ok"] += 1
            else:
                results["fail"] += 1
                results["errors"].append(
                    f"{handle}: HTTP {resp.status_code}"
                )
        except Exception as e:
            results["fail"] += 1
            results["errors"].append(f"{handle}: {e}")

    total = results["ok"] + results["fail"]

    if results["fail"] == total:
        logger.error(
            "TWITTER COOKIE DEAD - all %d probe requests failed. "
            "Errors: %s. Replace TWITTER_AUTH_TOKEN and restart rsshub.",
            total,
            "; ".join(results["errors"]),
        )
    elif results["fail"] > 0:
        logger.warning(
            "Twitter cookie degraded - %d/%d probes failed: %s",
            results["fail"],
            total,
            "; ".join(results["errors"]),
        )
    else:
        logger.info("Twitter cookie healthy - %d/%d probes OK", results["ok"], total)

    # Also check DB: any X sources with no data in the last 24h?
    _check_stale_x_sources(results)

    return results


def _check_stale_x_sources(results: dict):
    """Warn if Twitter sources haven't received data recently."""
    engine = create_engine(settings.database_url_sync)
    with Session(engine) as session:
        x_sources = session.execute(
            select(DataSource)
            .where(DataSource.id.like("G-X-%"))
            .where(DataSource.enabled.is_(True))
        ).scalars().all()

        stale = []
        for src in x_sources:
            last = session.execute(
                select(func.max(RawArticle.collected_at))
                .where(RawArticle.source_id == src.id)
            ).scalar()

            if last is None:
                stale.append(f"{src.id} (never collected)")

        if stale:
            results["stale_sources"] = stale
            logger.warning(
                "Twitter sources with no data: %s",
                ", ".join(stale[:10]),
            )

    engine.dispose()
