from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mine.db import get_db
from mine.models import DataSource

router = APIRouter()


class SourceCreate(BaseModel):
    id: str
    name: str
    region: str = "global"
    tier: str = "t2"
    crawler_type: str = "rss"
    crawler_config: dict = {}
    poll_interval_seconds: int = 3600


@router.get("/sources")
async def list_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DataSource).order_by(DataSource.tier, DataSource.name))
    sources = result.scalars().all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "region": s.region,
            "tier": s.tier,
            "crawler_type": s.crawler_type,
            "poll_interval_seconds": s.poll_interval_seconds,
            "enabled": s.enabled,
        }
        for s in sources
    ]


@router.post("/sources")
async def create_source(body: SourceCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.get(DataSource, body.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Source '{body.id}' already exists")
    source = DataSource(
        id=body.id,
        name=body.name,
        region=body.region,
        tier=body.tier,
        crawler_type=body.crawler_type,
        crawler_config=body.crawler_config,
        poll_interval_seconds=body.poll_interval_seconds,
    )
    db.add(source)
    await db.commit()
    return {"id": source.id, "name": source.name, "status": "created"}
