"""Unit tests for the ChatHistory service."""

import json
import tempfile
from pathlib import Path

import pytest

from app.models.chat_schemas import ChatMessage
from app.services.chat_history import ChatHistory


@pytest.fixture
def tmp_storage(tmp_path):
    """Create a temporary storage directory for chat history."""
    return str(tmp_path / "chat_history")


@pytest.fixture
def chat_history(tmp_storage):
    """Create a ChatHistory instance using a temporary directory."""
    return ChatHistory(storage_path=tmp_storage)


def _make_message(role: str, content: str, timestamp: str, sql: str | None = None, data: list[dict] | None = None) -> ChatMessage:
    """Helper to create a ChatMessage."""
    return ChatMessage(role=role, content=content, timestamp=timestamp, sql=sql, data=data)


class TestGetMessages:
    """Tests for get_messages method."""

    def test_returns_empty_list_when_no_history(self, chat_history):
        """get_messages returns empty list for a dataset with no history."""
        result = chat_history.get_messages("nonexistent-dataset")
        assert result == []

    def test_returns_messages_ordered_by_timestamp(self, chat_history):
        """get_messages returns messages sorted by timestamp ascending."""
        msg1 = _make_message("user", "First", "2024-01-01T10:00:00Z")
        msg3 = _make_message("user", "Third", "2024-01-01T12:00:00Z")
        msg2 = _make_message("assistant", "Second", "2024-01-01T11:00:00Z")

        # Save in non-chronological order
        chat_history.save_message("ds1", msg3)
        chat_history.save_message("ds1", msg1)
        chat_history.save_message("ds1", msg2)

        result = chat_history.get_messages("ds1")
        assert len(result) == 3
        assert result[0].content == "First"
        assert result[1].content == "Second"
        assert result[2].content == "Third"

    def test_respects_limit_parameter(self, chat_history):
        """get_messages returns at most `limit` messages."""
        for i in range(5):
            msg = _make_message("user", f"Message {i}", f"2024-01-01T1{i}:00:00Z")
            chat_history.save_message("ds1", msg)

        result = chat_history.get_messages("ds1", limit=3)
        assert len(result) == 3

    def test_default_limit_is_1000(self, chat_history):
        """get_messages has a default limit of 1000."""
        # Just verify it doesn't fail with default limit
        result = chat_history.get_messages("ds1")
        assert result == []

    def test_returns_all_when_fewer_than_limit(self, chat_history):
        """get_messages returns all messages when count is less than limit."""
        msg = _make_message("user", "Hello", "2024-01-01T10:00:00Z")
        chat_history.save_message("ds1", msg)

        result = chat_history.get_messages("ds1", limit=100)
        assert len(result) == 1


class TestGetRecentMessages:
    """Tests for get_recent_messages method."""

    def test_returns_empty_list_when_no_history(self, chat_history):
        """get_recent_messages returns empty list when no messages exist."""
        result = chat_history.get_recent_messages("nonexistent")
        assert result == []

    def test_returns_n_most_recent_in_chronological_order(self, chat_history):
        """get_recent_messages returns the N most recent messages oldest first."""
        for i in range(5):
            msg = _make_message("user", f"Message {i}", f"2024-01-01T1{i}:00:00Z")
            chat_history.save_message("ds1", msg)

        result = chat_history.get_recent_messages("ds1", limit=3)
        assert len(result) == 3
        # Should be the 3 most recent, in chronological order
        assert result[0].content == "Message 2"
        assert result[1].content == "Message 3"
        assert result[2].content == "Message 4"

    def test_returns_all_when_fewer_than_limit(self, chat_history):
        """get_recent_messages returns all messages when fewer than limit."""
        msg1 = _make_message("user", "Hello", "2024-01-01T10:00:00Z")
        msg2 = _make_message("assistant", "Hi", "2024-01-01T10:01:00Z")
        chat_history.save_message("ds1", msg1)
        chat_history.save_message("ds1", msg2)

        result = chat_history.get_recent_messages("ds1", limit=10)
        assert len(result) == 2
        assert result[0].content == "Hello"
        assert result[1].content == "Hi"

    def test_default_limit_is_10(self, chat_history):
        """get_recent_messages has a default limit of 10."""
        for i in range(15):
            msg = _make_message("user", f"Msg {i}", f"2024-01-01T10:{i:02d}:00Z")
            chat_history.save_message("ds1", msg)

        result = chat_history.get_recent_messages("ds1")
        assert len(result) == 10


class TestSaveMessage:
    """Tests for save_message method."""

    def test_persists_user_message(self, chat_history):
        """save_message persists a user message with all fields."""
        msg = _make_message("user", "What is the average?", "2024-01-01T10:00:00Z")
        chat_history.save_message("ds1", msg)

        result = chat_history.get_messages("ds1")
        assert len(result) == 1
        assert result[0].role == "user"
        assert result[0].content == "What is the average?"
        assert result[0].timestamp == "2024-01-01T10:00:00Z"
        assert result[0].sql is None
        assert result[0].data is None

    def test_persists_assistant_message_with_sql_and_data(self, chat_history):
        """save_message persists an assistant message with sql and data fields."""
        msg = ChatMessage(
            role="assistant",
            content="The average is 42.",
            sql="SELECT AVG(value) FROM dataset",
            data=[{"avg_value": 42}],
            timestamp="2024-01-01T10:01:00Z",
        )
        chat_history.save_message("ds1", msg)

        result = chat_history.get_messages("ds1")
        assert len(result) == 1
        assert result[0].role == "assistant"
        assert result[0].sql == "SELECT AVG(value) FROM dataset"
        assert result[0].data == [{"avg_value": 42}]

    def test_appends_to_existing_history(self, chat_history):
        """save_message appends to existing messages without overwriting."""
        msg1 = _make_message("user", "First", "2024-01-01T10:00:00Z")
        msg2 = _make_message("assistant", "Second", "2024-01-01T10:01:00Z")

        chat_history.save_message("ds1", msg1)
        chat_history.save_message("ds1", msg2)

        result = chat_history.get_messages("ds1")
        assert len(result) == 2

    def test_separate_datasets_are_isolated(self, chat_history):
        """Messages for different datasets don't interfere."""
        msg1 = _make_message("user", "Dataset A", "2024-01-01T10:00:00Z")
        msg2 = _make_message("user", "Dataset B", "2024-01-01T10:00:00Z")

        chat_history.save_message("ds-a", msg1)
        chat_history.save_message("ds-b", msg2)

        result_a = chat_history.get_messages("ds-a")
        result_b = chat_history.get_messages("ds-b")
        assert len(result_a) == 1
        assert result_a[0].content == "Dataset A"
        assert len(result_b) == 1
        assert result_b[0].content == "Dataset B"


class TestClear:
    """Tests for clear method."""

    def test_removes_all_messages(self, chat_history):
        """clear removes all messages for a dataset."""
        msg1 = _make_message("user", "Hello", "2024-01-01T10:00:00Z")
        msg2 = _make_message("assistant", "Hi", "2024-01-01T10:01:00Z")
        chat_history.save_message("ds1", msg1)
        chat_history.save_message("ds1", msg2)

        chat_history.clear("ds1")

        result = chat_history.get_messages("ds1")
        assert result == []

    def test_clear_nonexistent_dataset_does_not_raise(self, chat_history):
        """clear does not raise when called on a dataset with no history."""
        # Should not raise
        chat_history.clear("nonexistent")

    def test_clear_does_not_affect_other_datasets(self, chat_history):
        """clear only removes messages for the specified dataset."""
        msg1 = _make_message("user", "Dataset A", "2024-01-01T10:00:00Z")
        msg2 = _make_message("user", "Dataset B", "2024-01-01T10:00:00Z")
        chat_history.save_message("ds-a", msg1)
        chat_history.save_message("ds-b", msg2)

        chat_history.clear("ds-a")

        assert chat_history.get_messages("ds-a") == []
        assert len(chat_history.get_messages("ds-b")) == 1


class TestRoundTrip:
    """Tests for message storage round-trip integrity."""

    def test_message_fields_preserved_on_round_trip(self, chat_history):
        """All fields of a stored message are preserved when retrieved."""
        msg = ChatMessage(
            role="assistant",
            content="The top region is North with $45K average sales.",
            sql="SELECT region, AVG(sales) FROM dataset GROUP BY region ORDER BY AVG(sales) DESC LIMIT 1",
            data=[{"region": "North", "avg_sales": 45000}],
            timestamp="2024-01-15T10:30:02Z",
        )
        chat_history.save_message("ds1", msg)

        result = chat_history.get_messages("ds1")
        assert len(result) == 1
        retrieved = result[0]
        assert retrieved.role == msg.role
        assert retrieved.content == msg.content
        assert retrieved.sql == msg.sql
        assert retrieved.data == msg.data
        assert retrieved.timestamp == msg.timestamp
