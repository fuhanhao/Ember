import json
import logging
from datetime import datetime, timezone

from openai import OpenAI
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from mine.celery_app import celery
from mine.config import settings
from mine.models import RawArticle, TaggedArticle, DataSource

logger = logging.getLogger(__name__)

AI_KEYWORDS = [
    "ai", "artificial intelligence", "llm", "gpt", "openai", "anthropic", "claude",
    "deepseek", "gemini", "mistral", "llama", "machine learning", "deep learning",
    "neural", "transformer", "rag", "agent", "multimodal", "sora",
    "diffusion", "embedding", "finetune", "prompt", "huggingface", "pytorch",
    "tensorflow", "tutorial",
]

KEYWORD_TAGS = {
    "agent": "AI Agent",
    "rag": "RAG",
    "multimodal": "multimodal",
    "vision": "CV",
    "image": "AI image",
    "video": "AI video",
    "open source": "open source",
    "funding": "funding",
    "policy": "policy",
    "regulation": "policy",
    "chip": "AI chip",
    "gpu": "AI chip",
    "infra": "AI Infra",
    "security": "AI security",
    "safety": "AI security",
}

RULE_CATEGORY_BY_MEDIA = {
    "paper": "paper",
    "model": "model_release",
    "release": "open_source",
    "repository": "open_source",
    "tweet": "opinion",
    "discussion": "opinion",
    "video": "tutorial",
    "article": "opinion",
}

RULE_SIGNAL_BY_MEDIA = {
    "paper": 0.7,
    "model": 0.7,
    "release": 0.6,
    "repository": 0.55,
    "video": 0.5,
    "tweet": 0.4,
    "discussion": 0.4,
    "article": 0.4,
}


def rule_based_tag(title: str, content: str | None, media_type: str | None) -> dict:
    """Deterministic fallback tagging when no LLM key is available."""
    text = f"{title} {content or ''}".lower()
    is_ai_related = any(kw in text for kw in AI_KEYWORDS)
    if media_type in ("paper", "model", "release", "repository", "video", "tweet", "discussion"):
        is_ai_related = True

    tags = ["AI"]
    for kw, tag in KEYWORD_TAGS.items():
        if kw in text and tag not in tags:
            tags.append(tag)
    if "llm" in text or "gpt" in text or "model" in text:
        if "LLM" not in tags:
            tags.append("LLM")

    category = RULE_CATEGORY_BY_MEDIA.get(media_type or "", "opinion")
    content_signal = RULE_SIGNAL_BY_MEDIA.get(media_type or "", 0.4)
    if not is_ai_related:
        content_signal = 0.0

    return {
        "is_ai_related": is_ai_related,
        "title_zh": None,
        "category": category,
        "tags": tags[:8],
        "content_signal": content_signal,
    }

SYSTEM_PROMPT = """你是Ember数据引擎的标签分析模块。判断文章是否与AI/人工智能相关，并对AI领域文章做分类和标签提取。仅输出JSON。"""

USER_PROMPT_TEMPLATE = """来源: {source_name}
标题: {title}
正文: {content_first_800_chars}

输出:
{{
  "is_ai_related": true/false,
  "title_zh": "中文标题",
  "category": "从以下选一个: model_release, paper, product_launch, funding, policy, open_source, tutorial, opinion, industry_report, api_update, tool_review, market_data",
  "tags": ["从标签库匹配3-8个"],
  "content_signal": 0.0-1.0
}}

重要规则:
- title_zh: 如果原标题是中文则原样保留，如果是英文或其他语言则翻译为简洁的中文标题。保持新闻标题风格，不要加引号。
- is_ai_related: 文章主题是否与AI、人工智能、机器学习、大模型、深度学习直接相关。汽车降价、食品饮料、地产、体育、娱乐、时尚等非AI新闻必须标false。
- 如果is_ai_related=false，content_signal必须设为0.0

标签库: [LLM, NLP, CV, 多模态, 语音AI, AI Agent, RAG, 具身智能, AI安全, AI芯片, AI Infra, 开源模型, AI编程, AI绘画, AI视频, 数字人, 企业AI, AI医疗, AI教育, AI金融, AI电商, 融资, 政策法规, 独立开发, Prompt工程, AI变现, AI工作流]

content_signal 评分 (仅AI相关文章):
1.0 = 重大事件 (新模型发布, >$100M融资, 重大政策)
0.7 = 高影响 (开源项目, API降价, 重要论文)
0.5 = 中等 (产品更新, 工具评测, 教程)
0.3 = 一般 (普通AI新闻, 观点)
0.1 = 低价值 (重复报道, 搬运, 软广)"""


def calc_importance(source_tier: str, content_signal: float, published_at: datetime | None) -> float:
    source_weight = {"t1": 1.0, "t2": 0.7, "t3": 0.4, "t4": 0.2}.get(source_tier, 0.5)
    now = datetime.now(timezone.utc)
    if published_at:
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        hours = max(0, (now - published_at).total_seconds() / 3600)
    else:
        hours = 12  # default
    timeliness = 1 / (1 + hours / 24)
    return round(0.40 * source_weight + 0.35 * content_signal + 0.25 * timeliness, 4)


def call_llm(source_name: str, title: str, content: str | None) -> dict:
    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)

    content_snippet = (content or "")[:800]
    user_msg = USER_PROMPT_TEMPLATE.format(
        source_name=source_name,
        title=title,
        content_first_800_chars=content_snippet,
    )

    response = client.chat.completions.create(
        model=settings.openai_model_light,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.1,
    )

    raw_text = response.choices[0].message.content.strip()
    # Extract JSON from possible markdown code block
    if "```" in raw_text:
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    parsed = json.loads(raw_text)
    # LLM may return a list instead of dict — take the first element
    if isinstance(parsed, list):
        parsed = parsed[0] if parsed else {}
    return parsed


@celery.task(name="mine.tasks.tag_article", bind=True, max_retries=3)
def tag_article(self, raw_article_id: str):
    """Tag a single raw article with category, tags, and content_signal."""
    engine = create_engine(settings.database_url_sync)
    with Session(engine) as session:
        raw = session.get(RawArticle, raw_article_id)
        if not raw:
            logger.warning(f"Raw article {raw_article_id} not found")
            return

        # Skip if already tagged
        existing = session.execute(
            select(TaggedArticle).where(TaggedArticle.raw_article_id == raw_article_id)
        ).scalar_one_or_none()
        if existing:
            logger.info(f"Article {raw_article_id} already tagged")
            return

        source = session.get(DataSource, raw.source_id)
        source_name = source.name if source else raw.source_id
        source_tier = source.tier if source else "t2"

        llm_available = bool(settings.openai_api_key) and not settings.openai_api_key.startswith("sk-your")
        if llm_available:
            try:
                result = call_llm(source_name, raw.title, raw.content)
            except Exception as e:
                logger.error(f"LLM call failed for {raw_article_id}, using rule-based fallback: {e}")
                result = rule_based_tag(raw.title, raw.content, raw.media_type)
        else:
            logger.info(f"No usable OPENAI_API_KEY, using rule-based tagging for {raw_article_id}")
            result = rule_based_tag(raw.title, raw.content, raw.media_type)

        is_ai_related = result.get("is_ai_related", True)
        title_zh = result.get("title_zh") or raw.title
        category = result.get("category", "opinion").split("|")[0].strip()
        tags = result.get("tags", [])
        content_signal = float(result.get("content_signal", 0.3))
        content_signal = max(0.0, min(1.0, content_signal))

        if not is_ai_related:
            content_signal = 0.0

        importance = calc_importance(source_tier, content_signal, raw.published_at)

        tagged = TaggedArticle(
            raw_article_id=raw_article_id,
            title_zh=title_zh,
            category=category,
            tags=tags,
            content_signal=content_signal,
            importance_score=importance,
            is_ai_related=is_ai_related,
        )
        session.add(tagged)
        session.commit()
        logger.info(f"Tagged article {raw_article_id}: {category}, signal={content_signal}, importance={importance}")

    engine.dispose()
