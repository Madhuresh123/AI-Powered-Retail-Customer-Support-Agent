"""Database configuration and models for Neon Postgres storage."""

import os
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    LargeBinary,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DATABASE_URL = os.environ.get("DATABASE_URL", "")


class Base(DeclarativeBase):
    pass


class DatasetRecord(Base):
    """Stores dataset metadata and the Parquet binary data."""

    __tablename__ = "datasets"

    dataset_id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    row_count = Column(Integer, nullable=False)
    column_count = Column(Integer, nullable=False)
    source_type = Column(String(10), nullable=False)  # "csv" or "api"
    source_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    file_size_bytes = Column(Integer, nullable=False, default=0)
    parquet_data = Column(LargeBinary, nullable=False)  # The actual Parquet file bytes


class ChatMessageRecord(Base):
    """Stores chat history messages."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String(36), nullable=False, index=True)
    role = Column(String(10), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    sql = Column(Text, nullable=True)
    data = Column(Text, nullable=True)  # JSON string of row data
    timestamp = Column(String(50), nullable=False)


def get_engine():
    """Create SQLAlchemy engine from DATABASE_URL env var."""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    # Remove channel_binding param if present (not supported by all drivers)
    if "channel_binding" in url:
        parts = url.split("?")
        if len(parts) == 2:
            params = [p for p in parts[1].split("&") if "channel_binding" not in p]
            url = parts[0] + ("?" + "&".join(params) if params else "")
    # Use psycopg (v3) driver
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(url, pool_pre_ping=True, pool_size=5)


# Singleton engine and session factory
_engine = None
_session_factory = None


def get_cached_engine():
    """Get or create the singleton engine."""
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine


def get_session_factory():
    """Get or create the singleton sessionmaker."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_cached_engine())
    return _session_factory


def init_db():
    """Create all tables if they don't exist."""
    engine = get_engine()
    Base.metadata.create_all(engine)
