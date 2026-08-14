import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

from studio.db import get_db
from studio.models import NotebookItem, GeneratedContent, Notebook
from studio.api.deps import get_current_user_id
from studio.services.mine_client import mine_client
from studio.config import settings

import re

router = APIRouter(prefix="/generate", tags=["generate"])


def _parse_llm_json(raw: str) -> dict:
    """Robustly extract and repair JSON from LLM output."""
    # Strip markdown code fences
    if "```" in raw:
        parts = raw.split("```")
        for part in parts[1:]:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{") or part.startswith("["):
                raw = part
                break
    # Find the outermost JSON start
    start = None
    for i, ch in enumerate(raw):
        if ch in ('{', '['):
            start = i
            break
    if start is None:
        raise ValueError(f"No JSON found in LLM response: {raw[:200]}")

    snippet = raw[start:]

    # Try parsing complete JSON first
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        pass

    # Truncated JSON — progressively trim tail and close brackets
    # Remove character by character from end until we can close it
    for trim in range(min(200, len(snippet))):
        candidate = snippet if trim == 0 else snippet[:-trim]
        # Remove trailing partial tokens: comma, colon, whitespace
        candidate = candidate.rstrip(' \t\n\r,:')
        # Count open brackets
        braces = 0
        brackets = 0
        in_str = False
        esc = False
        for ch in candidate:
            if esc:
                esc = False
                continue
            if ch == '\\' and in_str:
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == '{': braces += 1
            elif ch == '}': braces -= 1
            elif ch == '[': brackets += 1
            elif ch == ']': brackets -= 1
        if in_str:
            continue  # still inside an unterminated string, trim more
        closed = candidate + (']' * brackets) + ('}' * braces)
        try:
            return json.loads(closed)
        except json.JSONDecodeError:
            continue

    raise ValueError(f"Could not repair JSON: {snippet[:200]}")


def _ensure_llm() -> None:
    """Raise a clear error before any LLM call when no key is configured."""
    if not settings.openai_api_key or settings.openai_api_key.startswith("sk-your"):
        raise HTTPException(
            status_code=400,
            detail="未配置 LLM API Key，生成功能暂不可用。请在 mine/.env 与 studio/.env 中配置 OPENAI_API_KEY。",
        )


llm = AsyncOpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)


class MindmapRequest(BaseModel):
    source_type: str  # article, notebook, document
    source_id: str


class KnowledgeGraphRequest(BaseModel):
    source_type: str
    source_id: str


class BlogRequest(BaseModel):
    source_type: str
    source_id: str
    style: str = "技术深度"
    tone: str = "专业严谨"
    length: str = "中篇2000字"
    target_platform: str = "通用Markdown"
    language: str = "zh"
    custom_instructions: str | None = None
    model: str | None = None


class ArticleRequest(BaseModel):
    source_type: str = ""
    source_id: str = ""
    output_type: str = "行业分析报告"
    language: str = "zh"
    custom_instructions: str | None = None
    model: str | None = None
    prompt: str | None = None
    context: str | None = None


async def _get_source_content(source_type: str, source_id: str, user_id: UUID, db: AsyncSession) -> tuple[str, str]:
    """Get content and title from source."""
    if source_type == "article":
        article = await mine_client.get_article(source_id)
        return article.get("content", "") or article.get("title", ""), article.get("title", "")
    elif source_type == "notebook":
        nb_id = UUID(source_id)
        result = await db.execute(
            NotebookItem.__table__.select().where(NotebookItem.notebook_id == nb_id)
        )
        items = result.fetchall()
        contents = [f"## {r.title}\n{r.content_cache or ''}" for r in items]
        nb = await db.get(Notebook, nb_id)
        return "\n\n".join(contents), nb.title if nb else "笔记本"
    elif source_type == "document":
        item = await db.get(NotebookItem, UUID(source_id))
        if item:
            return item.content_cache or "", item.title
    return "", ""


@router.post("/mindmap")
async def generate_mindmap(
    body: MindmapRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    _ensure_llm()
    content, title = await _get_source_content(body.source_type, body.source_id, user_id, db)
    if not content:
        raise HTTPException(status_code=400, detail="无法获取源内容")

    prompt = f"""从以下AI领域内容提取核心概念和层级关系。仅输出JSON:
{{
  "root": {{
    "text": "根节点(≤15字)",
    "children": [{{
      "text": "一级主题(≤15字)",
      "children": [{{"text": "二级要点(≤20字)", "children": []}}]
    }}]
  }}
}}
层级≤4, 每层节点≤6, 优先提取核心论点/关键数据/因果关系

内容:
{content[:4000]}"""

    async def stream():
        response = await llm.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=4096,
            stream=True,
        )
        full = ""
        async for chunk in response:
            if chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                full += text
                # Try to parse partial JSON and send it
                try:
                    partial = _parse_llm_json(full)
                    yield f"data: {json.dumps({'partial': partial}, ensure_ascii=False)}\n\n"
                except Exception:
                    pass

        # Final: parse the complete output
        try:
            final = _parse_llm_json(full)
        except Exception:
            final = {"root": {"text": title, "children": []}}

        # Save
        gen = GeneratedContent(
            user_id=user_id, source_type=body.source_type, source_id=body.source_id,
            output_type="mindmap", output_data={"mindmap": final, "title": title},
        )
        db.add(gen)
        await db.commit()
        yield f"data: {json.dumps({'done': True, 'mindmap': final, 'id': str(gen.id)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/knowledge-graph")
async def generate_kg(
    body: KnowledgeGraphRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    _ensure_llm()
    content, title = await _get_source_content(body.source_type, body.source_id, user_id, db)
    if not content:
        raise HTTPException(status_code=400, detail="无法获取源内容")

    # Step 1: Entity extraction
    entity_prompt = f"""从以下内容提取所有AI领域实体。输出JSON:
{{"entities": [{{"name":"...", "type":"company|person|model|product|technology|framework"}}]}}

内容:
{content[:4000]}"""

    resp1 = await llm.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": entity_prompt}],
        temperature=0.1,
    )
    entities_raw = resp1.choices[0].message.content.strip()
    entities = _parse_llm_json(entities_raw)

    # Step 2: Relation extraction
    relation_prompt = f"""分析以下实体之间的关系。输出JSON:
{{
  "nodes": [{{"id":"小写标识", "name":"显示名", "type":"...", "importance":1-5}}],
  "edges": [{{"source":"id1", "target":"id2", "relation":"研发|投资|竞争|合作|基于|替代|创始|发布|收购|使用", "weight":1-5}}]
}}
只输出高置信度关系。

实体: {json.dumps(entities, ensure_ascii=False)}

原文:
{content[:3000]}"""

    resp2 = await llm.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": relation_prompt}],
        temperature=0.1,
    )
    graph_raw = resp2.choices[0].message.content.strip()
    graph_json = _parse_llm_json(graph_raw)

    gen = GeneratedContent(
        user_id=user_id, source_type=body.source_type, source_id=body.source_id,
        output_type="knowledge_graph", output_data={"graph": graph_json, "entities": entities, "title": title},
    )
    db.add(gen)
    await db.commit()
    await db.refresh(gen)

    return {"id": str(gen.id), "graph": graph_json, "title": title}


@router.post("/blog")
async def generate_blog(
    body: BlogRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    _ensure_llm()
    content, title = await _get_source_content(body.source_type, body.source_id, user_id, db)
    if not content:
        raise HTTPException(status_code=400, detail="无法获取源内容")

    platform_instructions = {
        "微信公众号": """输出纯HTML格式（不要Markdown），可直接粘贴到微信公众号编辑器：
- 标题用 <h2 style="font-size:20px;font-weight:bold;color:#1a1a1a;margin:24px 0 12px;text-align:center"> 标签
- 小标题用 <h3 style="font-size:17px;font-weight:bold;color:#333;margin:20px 0 8px;border-left:4px solid #3478f6;padding-left:10px">
- 正文用 <p style="font-size:15px;line-height:2;color:#333;margin-bottom:16px;text-indent:0">
- 加粗用 <strong style="color:#1a1a1a">
- 引用用 <blockquote style="background:#f7f7f7;border-left:3px solid #3478f6;padding:12px 16px;margin:16px 0;font-size:14px;color:#666;line-height:1.8">
- 列表用 <ul style="margin:12px 0;padding-left:20px"><li style="font-size:15px;line-height:2;color:#333;margin-bottom:4px">
- 分隔线用 <hr style="border:none;border-top:1px dashed #ddd;margin:24px 0">
- 结尾来源用 <p style="font-size:12px;color:#999;margin-top:24px;text-align:center">
- 段落要短，每段2-3句，方便手机阅读
- 关键数据和结论加粗
- 开头要有吸引人的hook""",
        "知乎": "用Markdown格式，长段落，引用数据源，结尾提问互动",
        "即刻": "≤500字极简Markdown，直击要点",
        "Medium": "English Markdown with subheadings and code blocks",
        "通用Markdown": "标准Markdown格式",
    }
    fmt = platform_instructions.get(body.target_platform, platform_instructions["通用Markdown"])

    system = f"""你是专业内容创作者。直接输出文章正文，不要有任何开头寒暄、自我介绍、"好的"等废话。
风格:{body.style}, 语调:{body.tone}, 字数:{body.length}

{fmt}

严格要求:
1. 直接以文章标题开始，不要有"好的""以下是"等前缀
2. 不编造数据，有核心观点
3. 文末标注来源
{body.custom_instructions or ''}"""

    async def stream():
        response = await llm.chat.completions.create(
            model=body.model or settings.llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"基于以下材料撰写文章:\n\n{content[:6000]}"},
            ],
            stream=True,
        )
        full_content = ""
        async for chunk in response:
            if chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                full_content += text
                yield f"data: {json.dumps({'text': text}, ensure_ascii=False)}\n\n"

        # Save after streaming
        gen = GeneratedContent(
            user_id=user_id, source_type=body.source_type, source_id=body.source_id,
            output_type="blog",
            input_params=body.model_dump(),
            output_data={"content": full_content, "title": title},
        )
        db.add(gen)
        await db.commit()
        yield f"data: {json.dumps({'done': True, 'id': str(gen.id)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/article")
async def generate_article(
    body: ArticleRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    _ensure_llm()
    use_model = body.model or settings.llm_model

    # Free chat mode
    if body.prompt is not None:
        async def stream():
            response = await llm.chat.completions.create(
                model=use_model,
                messages=[
                    {"role": "system", "content": "你是FORGE AI助手，专注于AI行业分析和洞察。用中文回答，内容专业且有深度。直接回答问题，不要有开头寒暄或自我介绍。"},
                    {"role": "user", "content": body.prompt},
                ],
                stream=True,
            )
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    yield f"data: {json.dumps({'text': text}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        return StreamingResponse(stream(), media_type="text/event-stream")

    content, title = await _get_source_content(body.source_type, body.source_id, user_id, db)
    if not content:
        raise HTTPException(status_code=400, detail="无法获取源内容")

    outline_types = {
        "行业分析报告": "概览→玩家→趋势→商业化→风险→结论",
        "技术评测对比": "维度→逐项对比→评分→场景",
        "竞品分析": "定位→功能矩阵→差异化→SWOT→行动",
        "趋势预测": "现状→驱动→短期→中期→不确定性→行动",
    }
    structure = outline_types.get(body.output_type, "概览→分析→结论")

    system = f"""你是FORGE深度内容引擎。撰写{body.output_type}。
结构: {structure}
语言: {'中文' if body.language == 'zh' else 'English'}
要求: 数据驱动, 有深度洞察, 标注来源
{body.custom_instructions or ''}"""

    async def stream():
        response = await llm.chat.completions.create(
            model=use_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"基于以下材料撰写:\n\n{content[:8000]}"},
            ],
            stream=True,
        )
        full_content = ""
        async for chunk in response:
            if chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                full_content += text
                yield f"data: {json.dumps({'text': text}, ensure_ascii=False)}\n\n"

        gen = GeneratedContent(
            user_id=user_id, source_type=body.source_type, source_id=body.source_id,
            output_type="article",
            input_params=body.model_dump(),
            output_data={"content": full_content, "title": title},
        )
        db.add(gen)
        await db.commit()
        yield f"data: {json.dumps({'done': True, 'id': str(gen.id)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


class CategorySummaryRequest(BaseModel):
    category: str
    article_titles: list[str]
    article_snippets: list[str] = []


@router.post("/category-summary")
async def generate_category_summary(
    body: CategorySummaryRequest,
    user_id: UUID = Depends(get_current_user_id),
):
    _ensure_llm()
    titles = "\n".join(f"- {t}" for t in body.article_titles[:50])
    snippets = "\n\n".join(body.article_snippets[:20])[:4000] if body.article_snippets else ""

    prompt = f"""你是AI行业分析师。基于「{body.category}」分类下的文章，生成板块总结：
1. 核心趋势（2-3个要点）
2. 重要事件（最重要的3-5条）
3. 值得关注的信号

文章标题：
{titles}
{"内容片段：" + chr(10) + snippets if snippets else ""}

中文输出，简洁有深度，不超过500字。"""

    async def do_stream():
        response = await llm.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            stream=True, max_tokens=2048,
        )
        async for chunk in response:
            if chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                yield f"data: {json.dumps({'text': text}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    return StreamingResponse(do_stream(), media_type="text/event-stream")


class TranslateRequest(BaseModel):
    text: str
    target_lang: str = "zh"


@router.post("/translate")
async def translate_text(
    body: TranslateRequest,
    user_id: UUID = Depends(get_current_user_id),
):
    """Translate text to target language via LLM."""
    _ensure_llm()
    llm = AsyncOpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)

    async def do_stream():
        response = await llm.chat.completions.create(
            model=settings.llm_model_light,
            messages=[
                {"role": "system", "content": "你是专业翻译。将用户提供的文本翻译为简体中文。保持原文的段落结构。只输出翻译结果，不要任何解释。"},
                {"role": "user", "content": body.text},
            ],
            stream=True, max_tokens=4096, temperature=0.3,
        )
        async for chunk in response:
            if chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                yield f"data: {json.dumps({'text': text}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    return StreamingResponse(do_stream(), media_type="text/event-stream")
