from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from studio.db import get_db
from studio.models import GeneratedContent
from studio.api.deps import get_current_user_id

router = APIRouter(prefix="/generated", tags=["generated"])


@router.get("")
async def list_generated(
    type: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    query = select(GeneratedContent).where(GeneratedContent.user_id == user_id)
    if type:
        query = query.where(GeneratedContent.output_type == type)
    query = query.order_by(GeneratedContent.created_at.desc()).offset((page - 1) * limit).limit(limit)

    result = await db.execute(query)
    items = result.scalars().all()
    return [
        {
            "id": str(g.id),
            "output_type": g.output_type,
            "source_type": g.source_type,
            "title": g.output_data.get("title", ""),
            "created_at": g.created_at.isoformat() if g.created_at else None,
        }
        for g in items
    ]


@router.get("/{gen_id}")
async def get_generated(
    gen_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    gen = await db.get(GeneratedContent, gen_id)
    if not gen or gen.user_id != user_id:
        raise HTTPException(status_code=404)
    return {
        "id": str(gen.id),
        "output_type": gen.output_type,
        "source_type": gen.source_type,
        "input_params": gen.input_params,
        "output_data": gen.output_data,
        "created_at": gen.created_at.isoformat() if gen.created_at else None,
    }


@router.delete("/{gen_id}")
async def delete_generated(
    gen_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    gen = await db.get(GeneratedContent, gen_id)
    if not gen or gen.user_id != user_id:
        raise HTTPException(status_code=404)
    await db.delete(gen)
    await db.commit()
    return {"status": "deleted"}
