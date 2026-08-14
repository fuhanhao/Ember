from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from studio.db import get_db
from studio.models import Notebook, NotebookItem, UserDocument
from studio.api.deps import get_current_user_id
from studio.services.mine_client import mine_client

router = APIRouter(prefix="/notebooks", tags=["notebooks"])


class NotebookCreate(BaseModel):
    title: str
    description: str | None = None


class AddArticles(BaseModel):
    article_ids: list[str]


class AddDocument(BaseModel):
    type: str  # url, text, pdf, markdown
    content: str | None = None
    url: str | None = None


@router.post("")
async def create_notebook(
    body: NotebookCreate,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    nb = Notebook(user_id=user_id, title=body.title, description=body.description)
    db.add(nb)
    await db.commit()
    await db.refresh(nb)
    return {"id": str(nb.id), "title": nb.title}


@router.get("")
async def list_notebooks(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notebook)
        .where(Notebook.user_id == user_id)
        .order_by(Notebook.updated_at.desc())
    )
    notebooks = result.scalars().all()
    return [
        {"id": str(nb.id), "title": nb.title, "description": nb.description,
         "created_at": nb.created_at.isoformat() if nb.created_at else None}
        for nb in notebooks
    ]


@router.get("/{notebook_id}")
async def get_notebook(
    notebook_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    nb = await db.get(Notebook, notebook_id)
    if not nb or nb.user_id != user_id:
        raise HTTPException(status_code=404, detail="笔记本不存在")

    items_result = await db.execute(
        select(NotebookItem)
        .where(NotebookItem.notebook_id == notebook_id)
        .order_by(NotebookItem.created_at.desc())
    )
    items = items_result.scalars().all()

    return {
        "id": str(nb.id),
        "title": nb.title,
        "description": nb.description,
        "items": [
            {
                "id": str(item.id),
                "item_type": item.item_type,
                "title": item.title,
                "is_vectorized": item.is_vectorized,
                "mine_article_id": str(item.mine_article_id) if item.mine_article_id else None,
            }
            for item in items
        ],
    }


@router.put("/{notebook_id}")
async def update_notebook(
    notebook_id: UUID,
    body: NotebookCreate,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    nb = await db.get(Notebook, notebook_id)
    if not nb or nb.user_id != user_id:
        raise HTTPException(status_code=404)
    nb.title = body.title
    if body.description is not None:
        nb.description = body.description
    await db.commit()
    return {"status": "ok"}


@router.delete("/{notebook_id}")
async def delete_notebook(
    notebook_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    nb = await db.get(Notebook, notebook_id)
    if not nb or nb.user_id != user_id:
        raise HTTPException(status_code=404)
    await db.execute(delete(NotebookItem).where(NotebookItem.notebook_id == notebook_id))
    await db.delete(nb)
    await db.commit()
    return {"status": "deleted"}


@router.post("/{notebook_id}/articles")
async def add_articles(
    notebook_id: UUID,
    body: AddArticles,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    nb = await db.get(Notebook, notebook_id)
    if not nb or nb.user_id != user_id:
        raise HTTPException(status_code=404)

    articles = await mine_client.batch_articles(body.article_ids)
    added = 0
    for article in articles:
        item = NotebookItem(
            notebook_id=notebook_id,
            item_type="mine_article",
            mine_article_id=article["id"],
            content_cache=article.get("content"),
            title=article["title"],
        )
        db.add(item)
        added += 1

    await db.commit()
    # TODO: trigger async vectorization
    return {"added": added}


@router.post("/{notebook_id}/documents")
async def add_document(
    notebook_id: UUID,
    body: AddDocument,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    nb = await db.get(Notebook, notebook_id)
    if not nb or nb.user_id != user_id:
        raise HTTPException(status_code=404)

    content = body.content or ""
    title = "用户文档"

    if body.type == "url" and body.url:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(body.url)
                resp.raise_for_status()
                import re
                html = resp.text
                # Extract title
                m = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
                title = m.group(1) if m else body.url
                # Strip HTML
                content = re.sub(r'<[^>]+>', ' ', html)
                content = re.sub(r'\s+', ' ', content).strip()[:10000]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"无法获取URL内容: {e}")
    elif body.type in ("text", "markdown"):
        content = body.content or ""
        title = content[:50] + "..." if len(content) > 50 else content
    elif body.type == "pdf":
        raise HTTPException(status_code=501, detail="PDF导入开发中")

    item = NotebookItem(
        notebook_id=notebook_id,
        item_type="user_document",
        title=title,
        content_cache=content,
    )
    db.add(item)
    await db.flush()

    doc = UserDocument(
        notebook_item_id=item.id,
        user_id=user_id,
        content=content,
        source_url=body.url,
        file_type=body.type,
    )
    db.add(doc)
    await db.commit()
    # TODO: trigger async vectorization
    return {"item_id": str(item.id), "title": title}


@router.delete("/{notebook_id}/items/{item_id}")
async def delete_item(
    notebook_id: UUID,
    item_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    nb = await db.get(Notebook, notebook_id)
    if not nb or nb.user_id != user_id:
        raise HTTPException(status_code=404)
    item = await db.get(NotebookItem, item_id)
    if not item or item.notebook_id != notebook_id:
        raise HTTPException(status_code=404)
    await db.delete(item)
    await db.commit()
    return {"status": "deleted"}


@router.get("/{notebook_id}/items")
async def list_items(
    notebook_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    nb = await db.get(Notebook, notebook_id)
    if not nb or nb.user_id != user_id:
        raise HTTPException(status_code=404)
    result = await db.execute(
        select(NotebookItem)
        .where(NotebookItem.notebook_id == notebook_id)
        .order_by(NotebookItem.created_at.desc())
    )
    items = result.scalars().all()
    return [
        {
            "id": str(i.id),
            "item_type": i.item_type,
            "title": i.title,
            "is_vectorized": i.is_vectorized,
        }
        for i in items
    ]
