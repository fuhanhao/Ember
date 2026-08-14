import uuid

from sqlalchemy import Boolean, Date, Float, Integer, String, Text, Time, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(String(50))
    industry: Mapped[str | None] = mapped_column(String(100))
    interest_tags = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    language_preference: Mapped[str] = mapped_column(String(10), server_default="both")
    daily_brief_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    daily_brief_time = mapped_column(Time, server_default="08:00")
    breaking_news_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


class UserBehavior(Base):
    __tablename__ = "user_behaviors"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = mapped_column(UUID(as_uuid=True), nullable=False)
    article_id = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    created_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class Notebook(Base):
    __tablename__ = "notebooks"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


class NotebookItem(Base):
    __tablename__ = "notebook_items"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notebook_id = mapped_column(UUID(as_uuid=True), nullable=False)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    mine_article_id = mapped_column(UUID(as_uuid=True))
    content_cache: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    is_vectorized: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class UserDocument(Base):
    __tablename__ = "user_documents"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notebook_item_id = mapped_column(UUID(as_uuid=True), unique=True)
    user_id = mapped_column(UUID(as_uuid=True), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    file_type: Mapped[str | None] = mapped_column(String(20))
    created_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class GeneratedContent(Base):
    __tablename__ = "generated_contents"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = mapped_column(UUID(as_uuid=True), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id = mapped_column(UUID(as_uuid=True), nullable=False)
    output_type: Mapped[str] = mapped_column(String(50), nullable=False)
    input_params: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    output_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class DailyBrief(Base):
    __tablename__ = "daily_briefs"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = mapped_column(UUID(as_uuid=True), nullable=False)
    brief_date = mapped_column(Date, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = mapped_column(UUID(as_uuid=True), nullable=False)
    article_id = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
