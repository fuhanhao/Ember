from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from mine.db import get_db
from mine.models import TaggedArticle, RawArticle
import trafilatura

import re as _re

def _clean_content(text):
    if not text or len(text) < 50:
        return text
    if '<' in text and '>' in text:
        try:
            cleaned = trafilatura.extract(text, include_comments=False, include_tables=False, favor_precision=True)
            if cleaned and len(cleaned) > 50:
                return cleaned
        except Exception:
            pass
    text = _re.sub(r'^Title:.*$', '', text, flags=_re.MULTILINE)
    text = _re.sub(r'^URL Source:.*$', '', text, flags=_re.MULTILINE)
    text = _re.sub(r'^Published Time:.*$', '', text, flags=_re.MULTILINE)
    text = _re.sub(r'^Markdown Content:\s*', '', text, flags=_re.MULTILINE)
    text = _re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text)
    text = _re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
    return text.strip()




router = APIRouter()


@router.get("/articles")
async def list_articles(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    tags: Optional[str] = None,
    source_id: Optional[str] = None,
    region: Optional[str] = None,
    min_importance: Optional[float] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(TaggedArticle, RawArticle)
        .join(RawArticle, TaggedArticle.raw_article_id == RawArticle.id)
        .where(TaggedArticle.is_ai_related.is_(True))
        .order_by(RawArticle.published_at.desc().nulls_last(), TaggedArticle.importance_score.desc())
    )

    if category:
        query = query.where(TaggedArticle.category == category)
    if tags:
        tag_list = [t.strip() for t in tags.split(",")]
        query = query.where(TaggedArticle.tags.overlap(tag_list))
    if source_id:
        query = query.where(RawArticle.source_id == source_id)
    if min_importance is not None:
        query = query.where(TaggedArticle.importance_score >= min_importance)
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            since_dt = datetime.strptime(since, "%Y-%m-%d")
        query = query.where(RawArticle.collected_at >= since_dt)
    if until:
        try:
            until_dt = datetime.fromisoformat(until)
        except ValueError:
            until_dt = datetime.strptime(until, "%Y-%m-%d")
        query = query.where(RawArticle.collected_at < until_dt)

    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    return {
        "page": page,
        "limit": limit,
        "items": [
            {
                "id": str(tagged.id),
                "title": tagged.title_zh or raw.title,
                "url": raw.url,
                "source_id": raw.source_id,
                "author": raw.author,
                "published_at": raw.published_at.isoformat() if raw.published_at else None,
                "category": tagged.category,
                "tags": tagged.tags,
                "importance_score": tagged.importance_score,
                "content_signal": tagged.content_signal,
            }
            for tagged, raw in rows
        ],
    }


@router.get("/articles/{article_id}")
async def get_article(article_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TaggedArticle, RawArticle)
        .join(RawArticle, TaggedArticle.raw_article_id == RawArticle.id)
        .where(TaggedArticle.id == article_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Article not found")

    tagged, raw = row
    return {
        "id": str(tagged.id),
        "title": tagged.title_zh or raw.title,
        "url": raw.url,
        "content": _clean_content(raw.content),
        "source_id": raw.source_id,
        "author": raw.author,
        "published_at": raw.published_at.isoformat() if raw.published_at else None,
        "language": raw.language,
        "category": tagged.category,
        "tags": tagged.tags,
        "importance_score": tagged.importance_score,
        "content_signal": tagged.content_signal,
        "collected_at": raw.collected_at.isoformat() if raw.collected_at else None,
        "tagged_at": tagged.tagged_at.isoformat() if tagged.tagged_at else None,
    }


class BatchRequest(BaseModel):
    ids: list[UUID]


@router.post("/articles/batch")
async def batch_articles(req: BatchRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TaggedArticle, RawArticle)
        .join(RawArticle, TaggedArticle.raw_article_id == RawArticle.id)
        .where(TaggedArticle.id.in_(req.ids))
    )
    rows = result.all()
    return [
        {
            "id": str(tagged.id),
            "title": raw.title,
            "url": raw.url,
            "content": raw.content,
            "source_id": raw.source_id,
            "category": tagged.category,
            "tags": tagged.tags,
            "importance_score": tagged.importance_score,
            "content_signal": tagged.content_signal,
        }
        for tagged, raw in rows
    ]


@router.get("/hot")
async def hot_articles(
    limit: int = Query(20, ge=1, le=50),
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    cutoff = func.now() - func.make_interval(0, 0, 0, 0, hours)
    result = await db.execute(
        select(TaggedArticle, RawArticle)
        .join(RawArticle, TaggedArticle.raw_article_id == RawArticle.id)
        .where(RawArticle.published_at >= cutoff)
        .where(TaggedArticle.is_ai_related.is_(True))
        .order_by(TaggedArticle.importance_score.desc())
        .limit(limit)
    )
    rows = result.all()
    return [
        {
            "id": str(tagged.id),
            "title": tagged.title_zh or raw.title,
            "url": raw.url,
            "source_id": raw.source_id,
            "category": tagged.category,
            "tags": tagged.tags,
            "importance_score": tagged.importance_score,
            "published_at": raw.published_at.isoformat() if raw.published_at else None,
        }
        for tagged, raw in rows
    ]


@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db)):
    total = await db.execute(
        select(func.count(TaggedArticle.id)).where(TaggedArticle.is_ai_related.is_(True))
    )
    today_count = await db.execute(
        select(func.count(TaggedArticle.id))
        .join(RawArticle, TaggedArticle.raw_article_id == RawArticle.id)
        .where(
            RawArticle.collected_at >= func.current_date(),
            TaggedArticle.is_ai_related.is_(True),
        )
    )
    category_dist = await db.execute(
        select(TaggedArticle.category, func.count(TaggedArticle.id))
        .where(TaggedArticle.is_ai_related.is_(True))
        .group_by(TaggedArticle.category)
        .order_by(func.count(TaggedArticle.id).desc())
    )
    return {
        "total": total.scalar() or 0,
        "today": today_count.scalar() or 0,
        "categories": {row[0]: row[1] for row in category_dist.all()},
    }


@router.get("/stats/daily")
async def daily_stats(
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Return article count per day for the last N days (by collected_at)."""
    from sqlalchemy import cast, Date
    result = await db.execute(
        select(
            cast(RawArticle.collected_at, Date).label("day"),
            func.count(RawArticle.id),
        )
        .join(TaggedArticle, TaggedArticle.raw_article_id == RawArticle.id)
        .where(RawArticle.collected_at >= func.now() - func.make_interval(0, 0, 0, days))
        .where(TaggedArticle.is_ai_related.is_(True))
        .group_by("day")
        .order_by("day")
    )
    rows = {str(row[0]): row[1] for row in result.all()}

    # Fill gaps
    from datetime import date, timedelta
    today = date.today()
    series = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        series.append({"date": str(d), "count": rows.get(str(d), 0)})
    return series
