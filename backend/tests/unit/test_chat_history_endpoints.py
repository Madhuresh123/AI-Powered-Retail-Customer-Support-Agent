"""Unit tests for GET and DELETE /api/v1/chat/history endpoints."""

import uuid
from datetime import datetime, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_chat_history as get_chat_history_dep, get_dataset_service
from app.main import app
from app.models.chat_schemas import ChatMessage
from app.models.dataset import DatasetMetadata, SourceType
from app.services.chat_history import ChatHistory
from app.services.dataset_service import DatasetService


@pytest.fixture
def setup_services(tmp_path):
    """Create dataset service and chat history with temp storage."""
    dataset_dir = tmp_path / "datasets"
    dataset_dir.mkdir()
    chat_dir = tmp_path / "chat_history"
    chat_dir.mkdir()

    dataset_service = DatasetService(storage_path=str(dataset_dir))
    chat_history = ChatHistory(storage_path=str(chat_dir))

    # Store a dataset to make it "exist"
    df = pd.DataFrame({"name": ["Alice", "Bob"], "age": [30, 25]})
    meta = DatasetMetadata(
        dataset_id="",
        name="test.csv",
        row_count=2,
        column_count=2,
        source_type=SourceType.CSV,
        source_url=None,
        created_at=datetime(2024, 1, 10, 12, 0, 0, tzinfo=timezone.utc),
        file_size_bytes=0,
    )
    dataset_id = dataset_service.store(df, meta)

    app.dependency_overrides[get_dataset_service] = lambda: dataset_service
    app.dependency_overrides[get_chat_history_dep] = lambda: chat_history

    with TestClient(app) as client:
        yield client, dataset_id, chat_history

    app.dependency_overrides.clear()


class TestGetChatHistory:
    """Tests for GET /api/v1/chat/history."""

    def test_get_history_empty_returns_200_with_empty_array(self, setup_services):
        """When no messages exist, return HTTP 200 with empty array."""
        client, dataset_id, _ = setup_services
        response = client.get(f"/api/v1/chat/history?dataset_id={dataset_id}")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_history_returns_messages(self, setup_services):
        """When messages exist, return them as a JSON array."""
        client, dataset_id, chat_history = setup_services

        # Add some messages
        msg1 = ChatMessage(
            role="user",
            content="What is the average age?",
            sql=None,
            data=None,
            timestamp="2024-01-10T10:00:00Z",
        )
        msg2 = ChatMessage(
            role="assistant",
            content="The average age is 27.5.",
            sql="SELECT AVG(age) FROM dataset",
            data=None,
            timestamp="2024-01-10T10:00:01Z",
        )
        chat_history.save_message(dataset_id, msg1)
        chat_history.save_message(dataset_id, msg2)

        response = client.get(f"/api/v1/chat/history?dataset_id={dataset_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["role"] == "user"
        assert data[0]["content"] == "What is the average age?"
        assert data[1]["role"] == "assistant"
        assert data[1]["sql"] == "SELECT AVG(age) FROM dataset"

    def test_get_history_ordered_by_timestamp_ascending(self, setup_services):
        """Messages should be ordered by timestamp ascending."""
        client, dataset_id, chat_history = setup_services

        # Save messages out of order
        msg_later = ChatMessage(
            role="assistant",
            content="Later message",
            sql=None,
            data=None,
            timestamp="2024-01-10T12:00:00Z",
        )
        msg_earlier = ChatMessage(
            role="user",
            content="Earlier message",
            sql=None,
            data=None,
            timestamp="2024-01-10T10:00:00Z",
        )
        chat_history.save_message(dataset_id, msg_later)
        chat_history.save_message(dataset_id, msg_earlier)

        response = client.get(f"/api/v1/chat/history?dataset_id={dataset_id}")
        data = response.json()
        assert data[0]["timestamp"] == "2024-01-10T10:00:00Z"
        assert data[1]["timestamp"] == "2024-01-10T12:00:00Z"

    def test_get_history_missing_dataset_id_returns_422(self, setup_services):
        """Missing dataset_id query parameter returns 422."""
        client, _, _ = setup_services
        response = client.get("/api/v1/chat/history")
        assert response.status_code == 422
        assert response.json()["detail"] == "dataset_id query parameter is required"

    def test_get_history_empty_dataset_id_returns_422(self, setup_services):
        """Empty dataset_id query parameter returns 422."""
        client, _, _ = setup_services
        response = client.get("/api/v1/chat/history?dataset_id=")
        assert response.status_code == 422
        assert response.json()["detail"] == "dataset_id query parameter is required"

    def test_get_history_nonexistent_dataset_returns_404(self, setup_services):
        """Non-existent dataset_id returns 404."""
        client, _, _ = setup_services
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/chat/history?dataset_id={fake_id}")
        assert response.status_code == 404
        assert fake_id in response.json()["detail"]

    def test_get_history_response_contains_all_message_fields(self, setup_services):
        """Each message in the response has all required fields."""
        client, dataset_id, chat_history = setup_services

        msg = ChatMessage(
            role="user",
            content="Test question",
            sql=None,
            data=None,
            timestamp="2024-01-10T10:00:00Z",
        )
        chat_history.save_message(dataset_id, msg)

        response = client.get(f"/api/v1/chat/history?dataset_id={dataset_id}")
        data = response.json()
        assert len(data) == 1
        message = data[0]
        assert "role" in message
        assert "content" in message
        assert "sql" in message
        assert "data" in message
        assert "timestamp" in message


class TestClearChatHistory:
    """Tests for DELETE /api/v1/chat/history."""

    def test_clear_history_returns_204(self, setup_services):
        """Clearing history returns 204 with no body."""
        client, dataset_id, chat_history = setup_services

        # Add a message first
        msg = ChatMessage(
            role="user",
            content="Hello",
            sql=None,
            data=None,
            timestamp="2024-01-10T10:00:00Z",
        )
        chat_history.save_message(dataset_id, msg)

        response = client.delete(f"/api/v1/chat/history?dataset_id={dataset_id}")
        assert response.status_code == 204
        assert response.content == b""

    def test_clear_history_removes_all_messages(self, setup_services):
        """After clearing, GET returns empty array."""
        client, dataset_id, chat_history = setup_services

        msg = ChatMessage(
            role="user",
            content="Hello",
            sql=None,
            data=None,
            timestamp="2024-01-10T10:00:00Z",
        )
        chat_history.save_message(dataset_id, msg)

        # Clear
        client.delete(f"/api/v1/chat/history?dataset_id={dataset_id}")

        # Verify empty
        response = client.get(f"/api/v1/chat/history?dataset_id={dataset_id}")
        assert response.status_code == 200
        assert response.json() == []

    def test_clear_history_no_messages_still_returns_204(self, setup_services):
        """Clearing history for a dataset with no messages still returns 204."""
        client, dataset_id, _ = setup_services
        response = client.delete(f"/api/v1/chat/history?dataset_id={dataset_id}")
        assert response.status_code == 204
        assert response.content == b""

    def test_clear_history_missing_dataset_id_returns_422(self, setup_services):
        """Missing dataset_id query parameter returns 422."""
        client, _, _ = setup_services
        response = client.delete("/api/v1/chat/history")
        assert response.status_code == 422
        assert response.json()["detail"] == "dataset_id query parameter is required"

    def test_clear_history_empty_dataset_id_returns_422(self, setup_services):
        """Empty dataset_id query parameter returns 422."""
        client, _, _ = setup_services
        response = client.delete("/api/v1/chat/history?dataset_id=")
        assert response.status_code == 422
        assert response.json()["detail"] == "dataset_id query parameter is required"

    def test_clear_history_nonexistent_dataset_returns_404(self, setup_services):
        """Non-existent dataset_id returns 404."""
        client, _, _ = setup_services
        fake_id = str(uuid.uuid4())
        response = client.delete(f"/api/v1/chat/history?dataset_id={fake_id}")
        assert response.status_code == 404
        assert fake_id in response.json()["detail"]
