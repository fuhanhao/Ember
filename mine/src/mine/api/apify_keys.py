"""Apify API key pool management."""
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mine.db import get_db
from mine.models import ApifyKey

router = APIRouter()

APIFY_TEST_URL = "https://api.apify.com/v2/users/me"
APIFY_RUN_TEST_URL = "https://api.apify.com/v2/acts/danek~twitter-scraper-ppr/runs"


class ApifyKeyIn(BaseModel):
    api_key: str
    label: str | None = None


class ApifyKeyBatchIn(BaseModel):
    api_keys: list[str]


@router.get("/apify-keys")
async def list_keys(db: AsyncSession = Depends(get_db)):
    """List all Apify API keys with status."""
    rows = (await db.execute(
        select(ApifyKey).order_by(ApifyKey.added_at.desc())
    )).scalars().all()
    return [
        {
            "id": k.id,
            "key_preview": k.api_key[:8] + "..." + k.api_key[-4:],
            "label": k.label,
            "is_active": k.is_active,
            "status": k.status,
            "monthly_usage_usd": k.monthly_usage_usd,
            "added_at": k.added_at.isoformat() if k.added_at else None,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        }
        for k in rows
    ]


@router.post("/apify-keys")
async def add_key(body: ApifyKeyIn, db: AsyncSession = Depends(get_db)):
    """Add a single Apify API key."""
    key = body.api_key.strip()
    if not key or len(key) < 10:
        raise HTTPException(400, "API key too short")

    existing = (await db.execute(
        select(ApifyKey).where(ApifyKey.api_key == key)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(409, f"Key already exists (id={existing.id})")

    row = ApifyKey(api_key=key, label=body.label, status="untested")
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "status": "added"}


@router.post("/apify-keys/batch")
async def add_keys_batch(body: ApifyKeyBatchIn, db: AsyncSession = Depends(get_db)):
    """Batch add multiple Apify API keys."""
    added = []
    skipped = []
    for raw in body.api_keys:
        key = raw.strip()
        if not key or len(key) < 10:
            skipped.append({"key": key[:8] + "...", "reason": "too short"})
            continue
        existing = (await db.execute(
            select(ApifyKey).where(ApifyKey.api_key == key)
        )).scalar_one_or_none()
        if existing:
            skipped.append({"key": key[:8] + "...", "reason": "duplicate"})
            continue
        row = ApifyKey(api_key=key, status="untested")
        db.add(row)
        await db.flush()
        added.append({"id": row.id, "key_preview": key[:8] + "..."})

    await db.commit()
    return {"added": len(added), "skipped": len(skipped), "details": {"added": added, "skipped": skipped}}


@router.delete("/apify-keys/{key_id}")
async def remove_key(key_id: int, db: AsyncSession = Depends(get_db)):
    """Remove an Apify API key."""
    row = await db.get(ApifyKey, key_id)
    if not row:
        raise HTTPException(404, "Key not found")
    await db.delete(row)
    await db.commit()
    return {"status": "deleted", "id": key_id}


@router.patch("/apify-keys/{key_id}")
async def toggle_key(key_id: int, active: bool, db: AsyncSession = Depends(get_db)):
    """Enable or disable an Apify API key."""
    row = await db.get(ApifyKey, key_id)
    if not row:
        raise HTTPException(404, "Key not found")
    row.is_active = active
    await db.commit()
    return {"id": key_id, "is_active": active}


@router.post("/apify-keys/test/{key_id}")
async def test_key(key_id: int, db: AsyncSession = Depends(get_db)):
    """Test a single Apify API key by calling /v2/users/me."""
    row = await db.get(ApifyKey, key_id)
    if not row:
        raise HTTPException(404, "Key not found")

    now = datetime.now(timezone.utc)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(APIFY_TEST_URL, params={"token": row.api_key})
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            row.last_used_at = now
            username = data.get("username")
            plan = data.get("plan", {})
            usage = plan.get("usageTotal", {}).get("usd")
            if usage is not None:
                row.monthly_usage_usd = float(usage)

            # Check if monthly usage limit is exceeded
            limit_usd = plan.get("monthlyUsageCreditsUsd") or plan.get("usageLimitUsd")
            is_over_limit = False
            if limit_usd and usage is not None and float(usage) >= float(limit_usd):
                is_over_limit = True

            # Also try a real API call to verify
            if not is_over_limit:
                try:
                    check_resp = await client.get(
                        "https://api.apify.com/v2/acts",
                        params={"token": row.api_key, "limit": 1},
                        timeout=10,
                    )
                    if check_resp.status_code == 403:
                        is_over_limit = True
                except Exception:
                    pass

            if is_over_limit:
                row.status = "quota_exceeded"
                await db.commit()
                return {
                    "id": key_id,
                    "status": "quota_exceeded",
                    "username": username,
                    "monthly_usage_usd": row.monthly_usage_usd,
                }

            row.status = "healthy"
            await db.commit()
            return {
                "id": key_id,
                "status": "healthy",
                "username": username,
                "plan": plan.get("id"),
                "monthly_usage_usd": row.monthly_usage_usd,
            }
        else:
            row.status = "dead"
            row.last_used_at = now
            await db.commit()
            return {"id": key_id, "status": "dead", "http_code": resp.status_code}
    except Exception as e:
        row.status = "dead"
        row.last_used_at = now
        await db.commit()
        return {"id": key_id, "status": "dead", "error": str(e)}


@router.post("/apify-keys/test-all")
async def test_all_keys(db: AsyncSession = Depends(get_db)):
    """Test all active Apify API keys."""
    rows = (await db.execute(
        select(ApifyKey).where(ApifyKey.is_active.is_(True))
    )).scalars().all()

    results = []
    now = datetime.now(timezone.utc)
    async with httpx.AsyncClient(timeout=15) as client:
        for row in rows:
            try:
                resp = await client.get(APIFY_TEST_URL, params={"token": row.api_key})
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    plan = data.get("plan", {})
                    usage = plan.get("usageTotal", {}).get("usd")
                    if usage is not None:
                        row.monthly_usage_usd = float(usage)

                    # Check quota
                    limit_usd = plan.get("monthlyUsageCreditsUsd") or plan.get("usageLimitUsd")
                    is_over = False
                    if limit_usd and usage is not None and float(usage) >= float(limit_usd):
                        is_over = True
                    if not is_over:
                        try:
                            cr = await client.post(
                                APIFY_RUN_TEST_URL,
                                params={"token": row.api_key},
                                json={"username": "OpenAI", "max_posts": 1},
                                timeout=15,
                            )
                            if cr.status_code == 403:
                                is_over = True
                            elif cr.status_code == 201:
                                # Run started, abort it
                                run_id = cr.json().get("data", {}).get("id")
                                if run_id:
                                    await client.post(
                                        f"https://api.apify.com/v2/actor-runs/{run_id}/abort",
                                        params={"token": row.api_key},
                                        timeout=10,
                                    )
                        except Exception:
                            pass

                    if is_over:
                        row.status = "quota_exceeded"
                        results.append({"id": row.id, "status": "quota_exceeded", "usage_usd": row.monthly_usage_usd})
                    else:
                        row.status = "healthy"
                        results.append({"id": row.id, "status": "healthy", "usage_usd": row.monthly_usage_usd})
                else:
                    row.status = "dead"
                    results.append({"id": row.id, "status": "dead"})
            except Exception:
                row.status = "dead"
                results.append({"id": row.id, "status": "dead"})
            row.last_used_at = now

    await db.commit()
    healthy = sum(1 for r in results if r["status"] == "healthy")
    failed = len(results) - healthy
    return {"total": len(results), "healthy": healthy, "dead": failed, "details": results}
