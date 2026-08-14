"""Twitter cookie pool management API."""
import subprocess
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mine.db import get_db
from mine.models import TwitterCookie

router = APIRouter()

RSSHUB_BASE = "http://rsshub:1200"
ACCESS_KEY = "forge_mine_2026"
ENV_FILE_PATH = "/app/.env"


class CookieIn(BaseModel):
    auth_token: str
    label: str | None = None


@router.get("/twitter-cookies")
async def list_cookies(db: AsyncSession = Depends(get_db)):
    """List all Twitter cookies with status."""
    rows = (await db.execute(
        select(TwitterCookie).order_by(TwitterCookie.added_at.desc())
    )).scalars().all()
    return [
        {
            "id": c.id,
            "token_preview": c.auth_token[:8] + "..." + c.auth_token[-4:],
            "label": c.label,
            "is_active": c.is_active,
            "status": c.status,
            "added_at": c.added_at.isoformat() if c.added_at else None,
            "last_checked_at": c.last_checked_at.isoformat() if c.last_checked_at else None,
        }
        for c in rows
    ]


@router.post("/twitter-cookies")
async def add_cookie(body: CookieIn, db: AsyncSession = Depends(get_db)):
    """Add a new Twitter auth_token to the pool."""
    token = body.auth_token.strip()
    if not token or len(token) < 20:
        raise HTTPException(400, "auth_token too short, expected ~40 hex chars")

    existing = (await db.execute(
        select(TwitterCookie).where(TwitterCookie.auth_token == token)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(409, f"Token already exists (id={existing.id})")

    cookie = TwitterCookie(
        auth_token=token,
        label=body.label,
        status="untested",
    )
    db.add(cookie)
    await db.commit()
    await db.refresh(cookie)
    return {"id": cookie.id, "status": "added", "message": "Call POST /apply to activate"}


@router.delete("/twitter-cookies/{cookie_id}")
async def remove_cookie(cookie_id: int, db: AsyncSession = Depends(get_db)):
    """Remove a cookie from the pool."""
    cookie = await db.get(TwitterCookie, cookie_id)
    if not cookie:
        raise HTTPException(404, "Cookie not found")
    await db.delete(cookie)
    await db.commit()
    return {"status": "deleted", "id": cookie_id}


@router.post("/twitter-cookies/test/{cookie_id}")
async def test_cookie(cookie_id: int, db: AsyncSession = Depends(get_db)):
    """Test a single cookie by probing RSSHub Twitter route."""
    cookie = await db.get(TwitterCookie, cookie_id)
    if not cookie:
        raise HTTPException(404, "Cookie not found")

    now = datetime.now(timezone.utc)
    cookie.last_checked_at = now

    # Probe RSSHub Twitter route to check if current token works
    status = "dead"
    detail = ""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{RSSHUB_BASE}/twitter/user/OpenAI?key={ACCESS_KEY}",
                timeout=20,
            )
            body = resp.text
            if resp.status_code == 200 and "<item>" in body:
                status = "healthy"
                detail = "RSSHub 返回正常 Twitter 数据"
            elif "Authentication failed" in body or "Access denied" in body:
                status = "dead"
                detail = "Token 已失效：认证被拒绝"
            elif resp.status_code == 200:
                status = "dead"
                detail = "RSSHub 返回成功但无数据，Token 可能失效"
            else:
                status = "dead"
                detail = f"RSSHub 返回 HTTP {resp.status_code}"
    except httpx.TimeoutException:
        status = "dead"
        detail = "RSSHub 请求超时"
    except Exception as e:
        status = "dead"
        detail = f"连接失败: {str(e)[:100]}"

    cookie.status = status
    await db.commit()

    return {
        "id": cookie_id,
        "token_preview": cookie.auth_token[:8] + "...",
        "status": status,
        "detail": detail,
    }


@router.post("/twitter-cookies/apply")
async def apply_cookies(db: AsyncSession = Depends(get_db)):
    """Push all active cookies to RSSHub and restart it."""
    rows = (await db.execute(
        select(TwitterCookie)
        .where(TwitterCookie.is_active.is_(True))
        .order_by(TwitterCookie.id)
    )).scalars().all()

    if not rows:
        raise HTTPException(400, "No active cookies to apply")

    token_str = ",".join(c.auth_token for c in rows)

    # Update .env file
    try:
        with open(ENV_FILE_PATH, "r") as f:
            lines = f.readlines()

        new_lines = []
        token_written = False
        for line in lines:
            if line.startswith("TWITTER_AUTH_TOKEN="):
                new_lines.append(f"TWITTER_AUTH_TOKEN={token_str}\n")
                token_written = True
            else:
                new_lines.append(line)

        if not token_written:
            new_lines.append(f"\nTWITTER_AUTH_TOKEN={token_str}\n")

        with open(ENV_FILE_PATH, "w") as f:
            f.writelines(new_lines)
    except Exception as e:
        raise HTTPException(500, f"Failed to update .env: {e}")

    # Recreate RSSHub container with new env via docker compose
    restart_ok = False
    restart_msg = ""
    try:
        result = subprocess.run(
            ["docker", "compose", "-p", "mine", "-f", "/app/docker-compose.yml", "up", "-d", "rsshub"],
            capture_output=True, text=True, timeout=60,
        )
        restart_ok = result.returncode == 0
        restart_msg = result.stdout.strip() or result.stderr.strip()
    except Exception as e:
        restart_msg = str(e)

    # Verify after restart
    health = "unknown"
    if restart_ok:
        try:
            await _wait_and_probe()
            health = "healthy"
        except Exception:
            health = "probe_failed"

    return {
        "active_cookies": len(rows),
        "env_updated": True,
        "rsshub_restarted": restart_ok,
        "restart_detail": restart_msg.strip()[:200],
        "health": health,
    }


async def _wait_and_probe():
    """Wait for RSSHub to come back, then probe Twitter route."""
    import asyncio
    await asyncio.sleep(8)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{RSSHUB_BASE}/twitter/user/OpenAI?key={ACCESS_KEY}",
            timeout=20,
        )
        resp.raise_for_status()
