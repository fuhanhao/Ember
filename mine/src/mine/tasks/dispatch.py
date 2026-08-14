import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from mine.celery_app import celery
from mine.config import settings
from mine.models import DataSource, RawArticle

logger = logging.getLogger(__name__)


@celery.task(name="mine.tasks.crawl_dispatch")
def crawl_dispatch():
    """Check all enabled sources and dispatch crawl tasks for those that are due."""
    engine = create_engine(settings.database_url_sync)
    with Session(engine) as session:
        sources = session.execute(
            select(DataSource).where(DataSource.enabled.is_(True))
        ).scalars().all()

        now = datetime.now(timezone.utc)
        dispatched = 0

        for source in sources:
            # Find the most recent article collected from this source
            last_collected = session.execute(
                select(RawArticle.collected_at)
                .where(RawArticle.source_id == source.id)
                .order_by(RawArticle.collected_at.desc())
                .limit(1)
            ).scalar_one_or_none()

            should_crawl = True
            if last_collected:
                if last_collected.tzinfo is None:
                    last_collected = last_collected.replace(tzinfo=timezone.utc)
                elapsed = (now - last_collected).total_seconds()
                should_crawl = elapsed >= source.poll_interval_seconds

            if should_crawl:
                from mine.tasks.crawl import crawl_source
                crawl_source.delay(source.id)
                dispatched += 1
                logger.info(f"Dispatched crawl for: {source.id}")

        logger.info(f"Dispatch complete: {dispatched}/{len(sources)} sources triggered")

    engine.dispose()
