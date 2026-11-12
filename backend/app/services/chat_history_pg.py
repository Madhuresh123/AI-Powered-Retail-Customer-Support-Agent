"""Chat history service using Neon Postgres for storage."""

import json

from sqlalchemy.orm import Session

from app.database import ChatMessageRecord, get_session_factory
from app.models.chat_schemas import ChatMessage


class ChatHistoryPG:
    """Persistence layer for conversation messages using Postgres."""

    def __init__(self):
        self._session_factory = get_session_factory()

    def _get_session(self) -> Session:
        return self._session_factory()

    def get_messages(self, dataset_id: str, limit: int = 1000) -> list[ChatMessage]:
        """Get messages for a dataset, ordered by timestamp ascending."""
        with self._get_session() as session:
            records = (
                session.query(ChatMessageRecord)
                .filter(ChatMessageRecord.dataset_id == dataset_id)
                .order_by(ChatMessageRecord.timestamp.asc())
                .limit(limit)
                .all()
            )
            return [self._record_to_message(r) for r in records]

    def get_recent_messages(self, dataset_id: str, limit: int = 10) -> list[ChatMessage]:
        """Get the N most recent messages ordered chronologically (oldest first)."""
        with self._get_session() as session:
            # Get the most recent N messages
            records = (
                session.query(ChatMessageRecord)
                .filter(ChatMessageRecord.dataset_id == dataset_id)
                .order_by(ChatMessageRecord.timestamp.desc())
                .limit(limit)
                .all()
            )
            # Reverse to get chronological order (oldest first)
            records.reverse()
            return [self._record_to_message(r) for r in records]

    def save_message(self, dataset_id: str, message: ChatMessage) -> None:
        """Persist a single message."""
        data_json = json.dumps(message.data) if message.data else None

        record = ChatMessageRecord(
            dataset_id=dataset_id,
            role=message.role,
            content=message.content,
            sql=message.sql,
            data=data_json,
            timestamp=message.timestamp,
        )

        with self._get_session() as session:
            session.add(record)
            session.commit()

    def clear(self, dataset_id: str) -> None:
        """Remove all messages for a dataset."""
        with self._get_session() as session:
            session.query(ChatMessageRecord).filter(
                ChatMessageRecord.dataset_id == dataset_id
            ).delete()
            session.commit()

    def _record_to_message(self, record: ChatMessageRecord) -> ChatMessage:
        """Convert a DB record to a ChatMessage."""
        data = json.loads(record.data) if record.data else None
        return ChatMessage(
            role=record.role,
            content=record.content,
            sql=record.sql,
            data=data,
            timestamp=record.timestamp,
        )
