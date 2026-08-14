import logging

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from mine.celery_app import celery
from mine.config import settings
from mine.crawlers.rss import RssCrawler
from mine.crawlers.hn import HnApiCrawler
from mine.crawlers.github import GithubApiCrawler
from mine.crawlers.huggingface import HfApiCrawler
from mine.crawlers.podcast import PodcastRssCrawler
from mine.crawlers.email_imap import EmailImapCrawler
from mine.crawlers.web_scrape import WebScrapeCrawler
from mine.crawlers.apify_twitter import ApifyTwitterCrawler
from mine.crawlers.twitter_api_io import TwitterApiIoCrawler
from mine.crawlers.juejin import JuejinApiCrawler
from mine.crawlers.youtube import YoutubeCrawler
from mine.models import DataSource, RawArticle
from mine.utils.dedup import fingerprint_text, is_near_duplicate

logger = logging.getLogger(__name__)

CRAWLER_MAP = {
    "rss": RssCrawler,
    "hn_api": HnApiCrawler,
    "github_api": GithubApiCrawler,
    "hf_api": HfApiCrawler,
    "podcast_rss": PodcastRssCrawler,
    "email_imap": EmailImapCrawler,
    "web_scrape": WebScrapeCrawler,
    "apify_twitter": ApifyTwitterCrawler,
    "twitter_api_io": TwitterApiIoCrawler,
    "juejin_api": JuejinApiCrawler,
    "youtube_api": YoutubeCrawler,
}


@celery.task(name="mine.tasks.crawl_source", bind=True, max_retries=3)
def crawl_source(self, source_id: str):
    """Crawl a single data source by its ID."""
    engine = create_engine(settings.database_url_sync)
    with Session(engine) as session:
        source = session.get(DataSource, source_id)
        if not source or not source.enabled:
            logger.warning(f"Source {source_id} not found or disabled")
            return

        crawler_cls = CRAWLER_MAP.get(source.crawler_type)
        if not crawler_cls:
            logger.warning(f"No crawler for type: {source.crawler_type}")
            return

        crawler = crawler_cls(source_id=source.id, config=source.crawler_config or {})

        try:
            items = crawler.crawl()
        except Exception as e:
            logger.error(f"Crawl failed for {source_id}: {e}")
            raise self.retry(exc=e, countdown=60)

        new_count = 0
        new_ids = []
        for item in items:
            # URL dedup
            existing = session.execute(
                select(RawArticle.id).where(RawArticle.url == item.url)
            ).scalar_one_or_none()
            if existing:
                continue

            # Fingerprint dedup
            fp = fingerprint_text(item.title, item.content)

            # Check near-duplicates against recent articles from same source
            recent_fps = session.execute(
                select(RawArticle.fingerprint)
                .where(RawArticle.source_id == source_id)
                .where(RawArticle.fingerprint.isnot(None))
                .order_by(RawArticle.collected_at.desc())
                .limit(200)
            ).scalars().all()

            is_dup = any(is_near_duplicate(fp, rfp) for rfp in recent_fps if rfp)
            if is_dup:
                logger.debug(f"Near-duplicate skipped: {item.title[:50]}")
                continue

            raw = RawArticle(
                source_id=source_id,
                url=item.url,
                title=item.title,
                content=item.content,
                author=item.author,
                published_at=item.published_at,
                language=item.language,
                media_type=item.media_type,
                raw_metadata=item.raw_metadata,
                fingerprint=fp,
            )
            session.add(raw)
            session.flush()
            new_ids.append(str(raw.id))
            new_count += 1

        session.commit()
        logger.info(f"Crawled {source_id}: {len(items)} fetched, {new_count} new articles")

        # Trigger tagging after commit so articles exist in DB
        from mine.tasks.tag import tag_article
        for article_id in new_ids:
            tag_article.delay(article_id)

    engine.dispose()
