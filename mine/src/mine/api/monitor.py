from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case, text
from sqlalchemy.ext.asyncio import AsyncSession

from mine.db import get_db
from mine.models import DataSource, RawArticle, TaggedArticle

router = APIRouter()


@router.get("/monitor/sources")
async def source_health(db: AsyncSession = Depends(get_db)):
    """Per-source crawl health: last crawl time, article count, tag rate."""
    sources = (await db.execute(select(DataSource).order_by(DataSource.tier))).scalars().all()

    result = []
    for s in sources:
        # Total articles from this source
        total = (await db.execute(
            select(func.count(RawArticle.id)).where(RawArticle.source_id == s.id)
        )).scalar() or 0

        # Last collected time
        last = (await db.execute(
            select(RawArticle.collected_at)
            .where(RawArticle.source_id == s.id)
            .order_by(RawArticle.collected_at.desc())
            .limit(1)
        )).scalar()

        # Tagged count
        tagged = (await db.execute(
            select(func.count(TaggedArticle.id))
            .join(RawArticle, TaggedArticle.raw_article_id == RawArticle.id)
            .where(RawArticle.source_id == s.id)
        )).scalar() or 0

        # Hours since last crawl
        hours_ago = None
        if last:
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            hours_ago = round((datetime.now(timezone.utc) - last).total_seconds() / 3600, 1)

        status = "healthy"
        if total == 0:
            status = "no_data"
        elif hours_ago and hours_ago > (s.poll_interval_seconds / 3600 * 3):
            status = "stale"

        result.append({
            "id": s.id,
            "name": s.name,
            "tier": s.tier,
            "enabled": s.enabled,
            "total_articles": total,
            "tagged_articles": tagged,
            "tag_rate": round(tagged / total, 2) if total > 0 else 0,
            "last_crawl": last.isoformat() if last else None,
            "hours_since_crawl": hours_ago,
            "status": status,
        })

    return result


@router.get("/monitor/pipeline")
async def pipeline_stats(db: AsyncSession = Depends(get_db)):
    """Overall pipeline health: raw vs tagged, pending count."""
    total_raw = (await db.execute(select(func.count(RawArticle.id)))).scalar() or 0
    total_tagged = (await db.execute(select(func.count(TaggedArticle.id)))).scalar() or 0
    pending = total_raw - total_tagged

    # Today's numbers
    today_raw = (await db.execute(
        select(func.count(RawArticle.id))
        .where(RawArticle.collected_at >= func.current_date())
    )).scalar() or 0

    today_tagged = (await db.execute(
        select(func.count(TaggedArticle.id))
        .where(TaggedArticle.tagged_at >= func.current_date())
    )).scalar() or 0

    # Source count
    total_sources = (await db.execute(
        select(func.count(DataSource.id)).where(DataSource.enabled.is_(True))
    )).scalar() or 0

    return {
        "total_raw": total_raw,
        "total_tagged": total_tagged,
        "pending_tagging": pending,
        "today_raw": today_raw,
        "today_tagged": today_tagged,
        "active_sources": total_sources,
        "tag_success_rate": round(total_tagged / total_raw, 4) if total_raw > 0 else 0,
    }


@router.get("/monitor/failed")
async def failed_articles(db: AsyncSession = Depends(get_db)):
    """Articles that were collected but not yet tagged (potential failures)."""
    result = await db.execute(
        select(RawArticle)
        .outerjoin(TaggedArticle, TaggedArticle.raw_article_id == RawArticle.id)
        .where(TaggedArticle.id.is_(None))
        .order_by(RawArticle.collected_at.desc())
        .limit(50)
    )
    articles = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "source_id": a.source_id,
            "title": a.title,
            "url": a.url,
            "collected_at": a.collected_at.isoformat() if a.collected_at else None,
        }
        for a in articles
    ]


@router.post("/monitor/retry/{article_id}")
async def retry_tag(article_id: str, db: AsyncSession = Depends(get_db)):
    """Manually retry tagging a failed article."""
    from mine.tasks.tag import tag_article
    tag_article.delay(article_id)
    return {"status": "retry_dispatched", "article_id": article_id}


@router.get("/monitor/twitter-health")
async def twitter_health(db: AsyncSession = Depends(get_db)):
    """Twitter/X data source health: cookie status + per-KOL collection stats."""
    import httpx as _httpx

    # 1. Probe RSSHub Twitter route
    probe_handle = "OpenAI"
    rsshub_url = f"http://rsshub:1200/twitter/user/{probe_handle}?key=forge_mine_2026"
    try:
        resp = _httpx.get(rsshub_url, timeout=15)
        cookie_status = "healthy" if resp.status_code == 200 else f"error_{resp.status_code}"
    except Exception as e:
        cookie_status = f"unreachable: {e}"

    # 2. Per-source stats for all X sources
    x_sources = (await db.execute(
        select(DataSource).where(DataSource.id.like("G-X-%")).order_by(DataSource.tier)
    )).scalars().all()

    sources = []
    for s in x_sources:
        total = (await db.execute(
            select(func.count(RawArticle.id)).where(RawArticle.source_id == s.id)
        )).scalar() or 0

        last = (await db.execute(
            select(RawArticle.collected_at)
            .where(RawArticle.source_id == s.id)
            .order_by(RawArticle.collected_at.desc())
            .limit(1)
        )).scalar()

        hours_ago = None
        if last:
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            hours_ago = round((datetime.now(timezone.utc) - last).total_seconds() / 3600, 1)

        sources.append({
            "id": s.id,
            "name": s.name,
            "tier": s.tier,
            "total_articles": total,
            "last_crawl": last.isoformat() if last else None,
            "hours_since_crawl": hours_ago,
        })

    no_data = [s for s in sources if s["total_articles"] == 0]

    return {
        "cookie_status": cookie_status,
        "total_x_sources": len(sources),
        "sources_with_no_data": len(no_data),
        "sources": sources,
    }


@router.post("/monitor/retry-all")
async def retry_all_failed(db: AsyncSession = Depends(get_db)):
    """Retry tagging all failed articles."""
    result = await db.execute(
        select(RawArticle.id)
        .outerjoin(TaggedArticle, TaggedArticle.raw_article_id == RawArticle.id)
        .where(TaggedArticle.id.is_(None))
        .limit(200)
    )
    ids = [str(r) for r in result.scalars().all()]
    from mine.tasks.tag import tag_article
    for aid in ids:
        tag_article.delay(aid)
    return {"status": "retry_dispatched", "count": len(ids)}


@router.get("/monitor/proxy")
async def proxy_stats():
    """Proxy pool status: mode, alive/dead counts."""
    from mine.utils.http_client import get_proxy_pool
    pool = get_proxy_pool()
    return pool.stats()
