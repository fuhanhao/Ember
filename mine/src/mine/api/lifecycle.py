from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from mine.db import get_db
from mine.models import RawArticle, TaggedArticle

router = APIRouter()


@router.get("/lifecycle/stats")
async def lifecycle_stats(db: AsyncSession = Depends(get_db)):
    """Show article age distribution."""
    total = (await db.execute(select(func.count(RawArticle.id)))).scalar() or 0

    age_buckets = {}
    for label, days in [("7d", 7), ("30d", 30), ("60d", 60), ("90d", 90), ("90d+", 9999)]:
        if days == 9999:
            count = (await db.execute(
                select(func.count(RawArticle.id))
                .where(RawArticle.collected_at < func.now() - func.make_interval(0, 0, 0, 90))
            )).scalar() or 0
        else:
            prev = list(age_buckets.values())
            count = (await db.execute(
                select(func.count(RawArticle.id))
                .where(RawArticle.collected_at >= func.now() - func.make_interval(0, 0, 0, days))
            )).scalar() or 0
        age_buckets[label] = count

    return {"total": total, "age_distribution": age_buckets}


@router.post("/lifecycle/cleanup")
async def cleanup_old_articles(
    days: int = Query(90, ge=30),
    max_importance: float = Query(0.3, ge=0, le=1),
    dry_run: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """Archive/delete old low-importance articles.
    Default: dry_run=True (preview only, no deletion).
    """
    cutoff = func.now() - func.make_interval(0, 0, 0, days)

    # Find candidates
    candidates = await db.execute(
        select(func.count(RawArticle.id))
        .join(TaggedArticle, TaggedArticle.raw_article_id == RawArticle.id)
        .where(RawArticle.collected_at < cutoff)
        .where(TaggedArticle.importance_score <= max_importance)
    )
    count = candidates.scalar() or 0

    if dry_run or count == 0:
        return {"dry_run": True, "candidates": count, "deleted": 0}

    # Delete tagged first (FK constraint), then raw
    candidate_ids = await db.execute(
        select(RawArticle.id)
        .join(TaggedArticle, TaggedArticle.raw_article_id == RawArticle.id)
        .where(RawArticle.collected_at < cutoff)
        .where(TaggedArticle.importance_score <= max_importance)
    )
    ids = [r for r in candidate_ids.scalars().all()]

    await db.execute(delete(TaggedArticle).where(TaggedArticle.raw_article_id.in_(ids)))
    await db.execute(delete(RawArticle).where(RawArticle.id.in_(ids)))
    await db.commit()

    return {"dry_run": False, "candidates": count, "deleted": len(ids)}
