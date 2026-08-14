from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from studio.db import get_db
from studio.models import User
from studio.api.deps import get_current_user_id

router = APIRouter(prefix="/users", tags=["users"])


class OnboardingRequest(BaseModel):
    role: str
    industry: str | None = None
    interest_tags: list[str]
    language_preference: str = "both"


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None
    role: str | None = None
    industry: str | None = None
    interest_tags: list[str] | None = None
    language_preference: str | None = None
    daily_brief_enabled: bool | None = None
    breaking_news_enabled: bool | None = None


@router.post("/onboarding")
async def onboarding(
    body: OnboardingRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if len(body.interest_tags) < 3:
        raise HTTPException(status_code=400, detail="请至少选择3个兴趣标签")

    user.role = body.role
    user.industry = body.industry
    user.interest_tags = body.interest_tags
    user.language_preference = body.language_preference
    await db.commit()
    return {"status": "ok"}


@router.get("/me")
async def get_me(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404)
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "role": user.role,
        "industry": user.industry,
        "interest_tags": user.interest_tags or [],
        "language_preference": user.language_preference,
        "daily_brief_enabled": user.daily_brief_enabled,
        "breaking_news_enabled": user.breaking_news_enabled,
    }


@router.put("/me")
async def update_me(
    body: ProfileUpdate,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    return {"status": "ok"}
