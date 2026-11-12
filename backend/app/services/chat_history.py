"""Chat history service for persisting conversation messages as JSON files."""

import json
from pathlib import Path

from app.models.chat_schemas import ChatMessage


class ChatHistory:
    """Manages conversation message persistence using JSON files per dataset."""

    def __init__(self, storage_path: str = "/data/chat_history"):
        self.storage_path = Path(storage_path)
        self._ensure_storage_exists()

    def _ensure_storage_exists(self) -> None:
        """Create the storage directory if it doesn't exist."""
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, dataset_id: str) -> Path:
        """Get the JSON file path for a dataset's chat history."""
        return self.storage_path / f"{dataset_id}.json"

    def _read_messages(self, dataset_id: str) -> list[dict]:
        """Read raw message dicts from the JSON file."""
        file_path = self._get_file_path(dataset_id)
        if not file_path.exists():
            return []
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("messages", [])

    def _write_messages(self, dataset_id: str, messages: list[dict]) -> None:
        """Write message dicts to the JSON file."""
        file_path = self._get_file_path(dataset_id)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({"messages": messages}, f, indent=2)

    def get_messages(self, dataset_id: str, limit: int = 1000) -> list[ChatMessage]:
        """
        Get messages for a dataset, ordered by timestamp ascending.
        Returns at most `limit` messages.

        Args:
            dataset_id: The dataset identifier.
            limit: Maximum number of messages to return (default 1000).

        Returns:
            A list of ChatMessage objects ordered by timestamp ascending.
        """
        raw_messages = self._read_messages(dataset_id)
        # Sort by timestamp ascending
        raw_messages.sort(key=lambda m: m.get("timestamp", ""))
        # Apply limit
        raw_messages = raw_messages[:limit]
        return [ChatMessage(**msg) for msg in raw_messages]

    def get_recent_messages(self, dataset_id: str, limit: int = 10) -> list[ChatMessage]:
        """
        Get the N most recent messages ordered chronologically (oldest first).
        Used for prompt context.

        Args:
            dataset_id: The dataset identifier.
            limit: Number of most recent messages to return (default 10).

        Returns:
            A list of the N most recent ChatMessage objects ordered oldest first.
        """
        raw_messages = self._read_messages(dataset_id)
        # Sort by timestamp ascending
        raw_messages.sort(key=lambda m: m.get("timestamp", ""))
        # Take the last N messages (most recent), already in chronological order
        recent = raw_messages[-limit:] if len(raw_messages) > limit else raw_messages
        return [ChatMessage(**msg) for msg in recent]

    def save_message(self, dataset_id: str, message: ChatMessage) -> None:
        """
        Persist a single message.

        Args:
            dataset_id: The dataset identifier.
            message: The ChatMessage to persist.
        """
        raw_messages = self._read_messages(dataset_id)
        raw_messages.append(message.model_dump())
        self._write_messages(dataset_id, raw_messages)

    def clear(self, dataset_id: str) -> None:
        """
        Remove all messages for a dataset.

        Args:
            dataset_id: The dataset identifier.
        """
        file_path = self._get_file_path(dataset_id)
        if file_path.exists():
            file_path.unlink()
