import logging
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio.config import settings
from studio.db import get_db
from studio.models import User, UserBehavior, Bookmark, DailyBrief
from studio.api.deps import get_current_user_id
from studio.services.mine_client import mine_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["feed"])

ROLE_CATEGORY_BOOST = {
    "ai_engineer": ["paper", "open_source", "tutorial"],
    "student": ["paper", "open_source", "tutorial"],
    "founder": ["funding", "industry_report", "opinion"],
    "executive": ["funding", "industry_report", "opinion"],
    "investor": ["funding", "market_data", "policy"],
    "developer": ["open_source", "api_update", "tutorial"],
    "content_creator": ["tool_review", "tutorial", "product_launch"],
    "product_manager": ["product_launch", "industry_report", "tool_review"],
}

TIER_WEIGHT = {"t1": 1.0, "t2": 0.7, "t3": 0.4, "t4": 0.2}


def calc_feed_score(article: dict, user_tags: list[str], user_role: str | None) -> float:
    # Tag match ratio
    article_tags = set(article.get("tags", []))
    user_tag_set = set(user_tags)
    tag_match = len(article_tags & user_tag_set) / max(len(user_tag_set), 1)

    importance = article.get("importance_score", 0.5)

    # Recency
    from datetime import datetime, timezone
    recency = 0.5
    pub = article.get("published_at")
    if pub:
        try:
            dt = datetime.fromisoformat(pub)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            hours = max(0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600)
            recency = 1 / (1 + hours / 24)
        except Exception:
            pass

    score = 0.35 * tag_match + 0.30 * importance + 0.20 * recency + 0.15 * 0.7

    # Role boost
    if user_role:
        boost_cats = ROLE_CATEGORY_BOOST.get(user_role, [])
        if article.get("category") in boost_cats:
            score *= 1.3

    return round(score, 4)


CATEGORY_LABELS = {
    "paper": "论文",
    "model_release": "模型发布",
    "open_source": "开源项目",
    "funding": "融资动态",
    "product_launch": "产品发布",
    "opinion": "观点洞察",
    "industry_report": "行业报告",
    "tutorial": "教程资源",
    "policy": "政策法规",
    "market_data": "市场数据",
    "api_update": "API 更新",
    "tool_review": "工具测评",
}

CATEGORY_ICONS = {
    "paper": "📄",
    "model_release": "🤖",
    "open_source": "💻",
    "funding": "💰",
    "product_launch": "🚀",
    "opinion": "💡",
    "industry_report": "📊",
    "tutorial": "📚",
    "policy": "⚖️",
    "market_data": "📈",
    "api_update": "🔌",
    "tool_review": "🔧",
}


@router.get("/feed/stats")
async def get_stats():
    """Proxy Mine stats for dashboard."""
    return await mine_client.get_stats()


@router.get("/feed/stats/daily")
async def get_daily_stats(days: int = Query(30, ge=1, le=90)):
    """Proxy Mine daily stats for trending chart."""
    return await mine_client.get_daily_stats(days)


@router.get("/feed/daily-insight")
async def get_daily_insight(
    db: AsyncSession = Depends(get_db),
):
    """Return today's AI daily insight, generate if not cached."""
    today = date.today()

    # Check cache in DB
    existing = (await db.execute(
        select(DailyBrief)
        .where(DailyBrief.brief_date == today)
        .order_by(DailyBrief.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    if existing:
        return existing.content

    # Fetch today's top articles from Mine
    all_articles = []
    for pg in range(1, 4):
        try:
            data = await mine_client.get_articles(limit=100, page=pg)
            items = data.get("items", [])
            all_articles.extend(items)
            if len(items) < 100:
                break
        except Exception:
            break

    # Filter to recent high-importance articles
    top_articles = sorted(
        [a for a in all_articles if a.get("importance_score", 0) >= 0.4],
        key=lambda x: x.get("importance_score", 0),
        reverse=True,
    )[:30]

    if not top_articles:
        return {"insight": "暂无足够数据生成今日洞察", "generated_at": datetime.now(timezone.utc).isoformat()}

    # Build article summaries for LLM
    article_lines = []
    for a in top_articles:
        cat = CATEGORY_LABELS.get(a.get("category", ""), a.get("category", ""))
        article_lines.append(f"- [{cat}] {a['title']} (重要性:{a.get('importance_score', 0):.2f})")
    articles_text = "\n".join(article_lines)

    prompt = f"""你是 Ember 平台的资深 AI 行业编辑。请根据以下今日 AI 资讯标题，用中文写一句「今日洞察」。

今日资讯：
{articles_text}

严格要求：
1. 必须用中文回复
2. 只写一句话，30-60个汉字
3. 像资深科技媒体人发朋友圈的语气
4. 提炼今天最核心的趋势或变化，不要罗列
5. 不要用"今日"开头
6. 只返回这一句中文，不要有任何其他内容、标点符号以外的内容"""

    try:
        llm = AsyncOpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        resp = await llm.chat.completions.create(
            model=settings.llm_model_light,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.7,
        )
        raw_insight = resp.choices[0].message.content or ""
        logger.info(f"Daily insight raw response: {repr(raw_insight[:200])}")
        insight_text = raw_insight.strip().strip('"').strip("「」")
        if not insight_text or len(insight_text) < 10:
            insight_text = "AI 行业持续快速演进，基础设施和应用层都在加速迭代。"
    except Exception as e:
        logger.error(f"LLM daily insight generation failed: {e}")
        insight_text = "AI 行业持续快速演进，基础设施和应用层都在加速迭代。"

    content = {
        "insight": insight_text,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "article_count": len(top_articles),
    }

    # Cache to DB (user_id = zero UUID for global insight)
    brief = DailyBrief(
        user_id="00000000-0000-0000-0000-000000000000",
        brief_date=today,
        content=content,
    )
    db.add(brief)
    await db.commit()

    return content


@router.get("/feed/keywords")
async def get_keywords(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(20, ge=5, le=50),
):
    """Hot keywords for the last N hours, aggregated from Mine articles.

    Each keyword is weighted by article importance, so a high-importance
    paper mentioning a tag contributes more than a low-signal tweet.
    """
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    all_articles = []
    for pg in range(1, 6):
        try:
            data = await mine_client.get_articles(limit=100, page=pg, since=since)
            items = data.get("items", [])
            all_articles.extend(items)
            if len(items) < 100:
                break
        except Exception:
            break

    tag_weight: dict[str, float] = {}
    tag_count: dict[str, int] = {}
    for a in all_articles:
        importance = a.get("importance_score", 0.5) or 0.5
        for t in (a.get("tags") or []):
            if not t:
                continue
            tag_weight[t] = tag_weight.get(t, 0.0) + importance
            tag_count[t] = tag_count.get(t, 0) + 1

    keywords = [
        {
            "keyword": k,
            "score": round(v, 2),
            "count": tag_count.get(k, 0),
        }
        for k, v in sorted(tag_weight.items(), key=lambda x: x[1], reverse=True)[:limit]
    ]

    return {
        "since": since,
        "total_articles": len(all_articles),
        "keywords": keywords,
    }


# Add this endpoint to feed.py - generates daily briefing by category

@router.get("/feed/daily-briefing")
async def get_daily_briefing(
    db: AsyncSession = Depends(get_db),
):
    """Generate yesterday's AI daily briefing grouped by category."""
    from datetime import timedelta
    today = date.today()
    yesterday = today - timedelta(days=1)
    # Fall back to today when yesterday has no data (e.g. first day of use)
    brief_date = yesterday
    all_articles = []
    for candidate in (yesterday, today):
        tmp: list = []
        for pg in range(1, 6):
            try:
                data = await mine_client.get_articles(
                    limit=100, page=pg,
                    since=candidate.isoformat(),
                    until=(candidate + timedelta(days=1)).isoformat(),
                )
                items = data.get("items", [])
                tmp.extend(items)
                if len(items) < 100:
                    break
            except Exception:
                break
        if tmp:
            brief_date = candidate
            all_articles = tmp
            break

    # Check cache
    existing = (await db.execute(
        select(DailyBrief)
        .where(DailyBrief.brief_date == brief_date)
        .where(DailyBrief.user_id == "00000000-0000-0000-0000-000000000001")
        .order_by(DailyBrief.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    if existing and existing.content:
        cached = existing.content
        cached_sections = cached.get("sections") or []
        cached_summary = cached.get("summary") or ""
        # A stale cache (empty sections / failed generation) should regenerate.
        if cached_sections or ("失败" not in cached_summary and "暂无" not in cached_summary):
            return cached

    if not all_articles:
        return {"date": brief_date.isoformat(), "sections": [], "summary": "昨日暂无 AI 相关资讯"}

    # Group by category
    from collections import defaultdict
    groups: dict[str, list] = defaultdict(list)
    for a in all_articles:
        cat = a.get("category", "other")
        groups[cat].append(a)

    # Sort groups by article count desc
    sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)

    # Build prompt for each category
    category_blocks = []
    for cat, arts in sorted_groups[:8]:
        label = CATEGORY_LABELS.get(cat, cat)
        titles = [f"- {a['title']} (重要性:{a.get('importance_score',0):.1f})" for a in sorted(arts, key=lambda x: x.get('importance_score',0), reverse=True)[:10]]
        category_blocks.append(f"## {label}（{len(arts)}篇）\n" + "\n".join(titles))

    all_blocks = "\n\n".join(category_blocks)

    prompt = f"""你是 Ember 平台的资深 AI 行业编辑。请根据以下 {brief_date.isoformat()} 的 AI 资讯，生成一份「AI 昨日日报」。

{all_blocks}

严格要求：
1. 必须用中文
2. 按分类输出，每个分类写 2-4 句话总结该领域昨天发生的关键事件和趋势
3. 只总结有实质内容的分类，跳过文章太少或不重要的分类
4. 语气专业、简洁，像科技媒体主编写的晨报
5. 最后用一句话给出整体趋势判断
6. 输出格式严格为 JSON：
{{
  "summary": "一句话整体趋势",
  "sections": [
    {{"category": "分类名", "title": "该分类小标题(8字以内)", "content": "2-4句总结", "article_count": 数量}}
  ]
}}
只输出 JSON，不要其他内容。"""

    try:
        api_key = settings.briefing_api_key or settings.openai_api_key
        llm = AsyncOpenAI(api_key=api_key, base_url=settings.openai_base_url)
        resp = await llm.chat.completions.create(
            model=settings.briefing_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.4,
        )
        raw = resp.choices[0].message.content or ""
        logger.info(f"Daily briefing raw: {raw[:300]}")

        # Parse JSON
        import json, re
        # Strip markdown fences
        cleaned = re.sub(r'```json?\s*', '', raw)
        cleaned = re.sub(r'```', '', cleaned).strip()
        result = json.loads(cleaned)
    except Exception as e:
        logger.error(f"Daily briefing generation failed: {e}")
        # Rule-based fallback so the briefing panel always has content,
        # even when no LLM key is configured.
        sections = []
        for cat, arts in sorted_groups[:6]:
            top_titles = [
                a["title"]
                for a in sorted(arts, key=lambda x: x.get("importance_score", 0), reverse=True)[:3]
            ]
            sections.append({
                "category": cat,
                "title": CATEGORY_LABELS.get(cat, cat),
                "content": "；".join(f"《{t}》" for t in top_titles) or "暂无摘要",
                "article_count": len(arts),
            })
        result = {
            "summary": f"共采集 {len(all_articles)} 篇 AI 相关资讯，热点集中在论文、开源项目与模型发布。",
            "sections": sections,
        }

    content = {
        "date": brief_date.isoformat(),
        **result,
        "total_articles": len(all_articles),
    }

    # Cache
    brief = DailyBrief(
        user_id="00000000-0000-0000-0000-000000000001",
        brief_date=brief_date,
        content=content,
    )
    db.add(brief)
    await db.commit()

    return content


@router.get("/feed/digest")
async def get_digest(
    since: str | None = None,
    until: str | None = None,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Return articles grouped by category, sorted by importance within each group."""
    user = await db.get(User, user_id)
    user_tags = user.interest_tags or [] if user else []
    user_role = user.role if user else None

    # Fetch articles from Mine
    all_articles = []
    for pg in range(1, 6):
        try:
            extra: dict = {}
            if since:
                extra["since"] = since
            if until:
                extra["until"] = until
            data = await mine_client.get_articles(limit=100, page=pg, **extra)
            items = data.get("items", [])
            all_articles.extend(items)
            if len(items) < 100:
                break
        except Exception:
            break

    # Get viewed article IDs
    viewed = await db.execute(
        select(UserBehavior.article_id)
        .where(UserBehavior.user_id == user_id)
        .where(UserBehavior.action.in_(["view", "read"]))
    )
    viewed_ids = {str(r) for r in viewed.scalars().all()}

    # Score and group by category
    from collections import defaultdict
    groups: dict[str, list[dict]] = defaultdict(list)
    for a in all_articles:
        if a["id"] in viewed_ids:
            continue
        a["feed_score"] = calc_feed_score(a, user_tags, user_role)
        cat = a.get("category", "other")
        groups[cat].append(a)

    # Sort each group by importance, build result
    result = []
    for cat, articles in groups.items():
        articles.sort(key=lambda x: x.get("importance_score", 0), reverse=True)
        result.append({
            "category": cat,
            "label": CATEGORY_LABELS.get(cat, cat),
            "icon": CATEGORY_ICONS.get(cat, "📰"),
            "total": len(articles),
            "top_importance": articles[0].get("importance_score", 0) if articles else 0,
            "preview": articles[:5],
        })

    # Sort groups: by top importance desc
    result.sort(key=lambda g: g["top_importance"], reverse=True)

    return {"groups": result}


@router.get("/feed")
async def get_feed(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    category: str | None = None,
    tag: str | None = None,
    since: str | None = None,
    until: str | None = None,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    user_tags = user.interest_tags or [] if user else []
    user_role = user.role if user else None

    # Fetch candidates from Mine (multiple pages)
    all_articles = []
    seen_ids = set()
    for p in range(1, 6):  # up to 500 articles
        params = {"limit": 100, "page": p}
        if category:
            params["category"] = category
        if tag:
            params["tags"] = tag
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        try:
            data = await mine_client.get_articles(**params)
            items = data.get("items", [])
            for item in items:
                if item["id"] not in seen_ids:
                    seen_ids.add(item["id"])
                    all_articles.append(item)
            if len(items) < 100:
                break
        except Exception:
            break
    articles = all_articles

    # Get viewed article IDs
    viewed = await db.execute(
        select(UserBehavior.article_id)
        .where(UserBehavior.user_id == user_id)
        .where(UserBehavior.action.in_(["view", "read"]))
    )
    viewed_ids = {str(r) for r in viewed.scalars().all()}

    # Score, filter viewed, sort
    scored = []
    for a in articles:
        if a["id"] in viewed_ids:
            continue
        a["feed_score"] = calc_feed_score(a, user_tags, user_role)
        scored.append(a)

    scored.sort(key=lambda x: x["feed_score"], reverse=True)

    # Paginate
    start = (page - 1) * limit
    page_items = scored[start:start + limit]

    return {"page": page, "limit": limit, "total": len(scored), "items": page_items}


@router.get("/article/{article_id}")
async def get_article(article_id: str, user_id: UUID = Depends(get_current_user_id)):
    return await mine_client.get_article(article_id)


@router.post("/article/{article_id}/action")
async def record_action(
    article_id: str,
    action: str,
    duration_seconds: int | None = None,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    behavior = UserBehavior(
        user_id=user_id,
        article_id=article_id,
        action=action,
        duration_seconds=duration_seconds,
    )
    db.add(behavior)
    await db.commit()
    return {"status": "ok"}


@router.get("/bookmarks")
async def list_bookmarks(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Bookmark)
        .where(Bookmark.user_id == user_id)
        .order_by(Bookmark.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    bookmarks = result.scalars().all()
    ids = [str(b.article_id) for b in bookmarks]
    if not ids:
        return {"page": page, "items": []}
    articles = await mine_client.batch_articles(ids)
    return {"page": page, "items": articles}


@router.post("/bookmarks/{article_id}")
async def add_bookmark(
    article_id: str,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    bookmark = Bookmark(user_id=user_id, article_id=article_id)
    db.add(bookmark)
    await db.commit()
    return {"status": "bookmarked"}


@router.delete("/bookmarks/{article_id}")
async def remove_bookmark(
    article_id: str,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import delete
    await db.execute(
        delete(Bookmark)
        .where(Bookmark.user_id == user_id)
        .where(Bookmark.article_id == article_id)
    )
    await db.commit()
    return {"status": "removed"}


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    category: str | None = None,
    tag: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    user_id: UUID = Depends(get_current_user_id),
):
    # Use Mine API with filtering; MVP uses title matching
    params = {"page": page, "limit": limit}
    if category:
        params["category"] = category
    if tag:
        params["tags"] = tag
    data = await mine_client.get_articles(**params)
    # Client-side filter by query
    q_lower = q.lower()
    items = [a for a in data.get("items", []) if q_lower in a.get("title", "").lower()
             or q_lower in " ".join(a.get("tags", [])).lower()]
    return {"query": q, "page": page, "items": items}
