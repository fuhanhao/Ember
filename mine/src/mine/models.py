import uuid

from sqlalchemy import Boolean, Float, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    region: Mapped[str] = mapped_column(String(10), nullable=False)
    tier: Mapped[str] = mapped_column(String(10), nullable=False)
    crawler_type: Mapped[str] = mapped_column(String(50), nullable=False)
    crawler_config: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    poll_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class RawArticle(Base):
    __tablename__ = "raw_articles"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(255))
    published_at = mapped_column(TIMESTAMP(timezone=True))
    language: Mapped[str | None] = mapped_column(String(10))
    media_type: Mapped[str | None] = mapped_column(String(50))
    raw_metadata: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    collected_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    fingerprint: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        Index("idx_raw_source", "source_id"),
        Index("idx_raw_published", published_at.desc()),
    )


class TwitterCookie(Base):
    __tablename__ = "twitter_cookies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    auth_token: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(100))  # e.g. "account-1"
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    added_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    last_checked_at = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), server_default="'untested'")  # untested, healthy, dead


class ApifyKey(Base):
    __tablename__ = "apify_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    api_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    added_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    last_used_at = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    monthly_usage_usd: Mapped[float] = mapped_column(Float, server_default="0.0")
    status: Mapped[str] = mapped_column(String(20), server_default="untested")  # untested, healthy, dead, quota_exceeded


class TaggedArticle(Base):
    __tablename__ = "tagged_articles"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_article_id = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    tags = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    content_signal: Mapped[float] = mapped_column(Float, nullable=False)
    importance_score: Mapped[float] = mapped_column(Float, nullable=False)
    title_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_ai_related: Mapped[bool] = mapped_column(Boolean, server_default="true")
    tagged_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_tag_category", "category"),
        Index("idx_tag_importance", importance_score.desc()),
        Index("idx_tag_tags", "tags", postgresql_using="gin"),
    )
