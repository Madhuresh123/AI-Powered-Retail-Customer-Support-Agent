"""Unit tests for the dataset management endpoints (list, detail, delete)."""

import uuid
from datetime import datetime, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_dataset_service
from app.main import app
from app.models.dataset import DatasetMetadata, SourceType
from app.services.dataset_service import DatasetService


@pytest.fixture
def client(tmp_path):
    """Create a test client with a temp storage directory."""
    storage_dir = tmp_path / "datasets"
    storage_dir.mkdir()

    service = DatasetService(storage_path=str(storage_dir))

    app.dependency_overrides[get_dataset_service] = lambda: service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def populated_client(tmp_path):
    """Create a test client with some pre-stored datasets."""
    storage_dir = tmp_path / "datasets"
    storage_dir.mkdir()

    service = DatasetService(storage_path=str(storage_dir))

    # Store two datasets
    df1 = pd.DataFrame({"name": ["Alice", "Bob"], "age": [30, 25]})
    meta1 = DatasetMetadata(
        dataset_id="",
        name="users.csv",
        row_count=2,
        column_count=2,
        source_type=SourceType.CSV,
        source_url=None,
        created_at=datetime(2024, 1, 10, 12, 0, 0, tzinfo=timezone.utc),
        file_size_bytes=0,
    )
    id1 = service.store(df1, meta1)

    df2 = pd.DataFrame({"city": ["NYC", "LA", "SF"], "pop": [8000000, 4000000, 900000]})
    meta2 = DatasetMetadata(
        dataset_id="",
        name="cities.csv",
        row_count=3,
        column_count=2,
        source_type=SourceType.CSV,
        source_url=None,
        created_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        file_size_bytes=0,
    )
    id2 = service.store(df2, meta2)

    app.dependency_overrides[get_dataset_service] = lambda: service
    with TestClient(app) as c:
        yield c, id1, id2
    app.dependency_overrides.clear()


class TestListDatasets:
    """Tests for GET /api/v1/datasets."""

    def test_list_empty_store(self, client):
        """Test that an empty store returns 200 with an empty array."""
        response = client.get("/api/v1/datasets")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_returns_all_datasets(self, populated_client):
        """Test that all stored datasets are returned."""
        client, id1, id2 = populated_client
        response = client.get("/api/v1/datasets")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        ids = [item["dataset_id"] for item in data]
        assert id1 in ids
        assert id2 in ids

    def test_list_ordered_by_created_at_descending(self, populated_client):
        """Test that datasets are ordered by creation time descending."""
        client, id1, id2 = populated_client
        response = client.get("/api/v1/datasets")
        data = response.json()
        # id2 was created on Jan 15, id1 on Jan 10 — id2 should be first
        assert data[0]["dataset_id"] == id2
        assert data[1]["dataset_id"] == id1

    def test_list_contains_required_fields(self, populated_client):
        """Test that each item has dataset_id, name, row_count, created_at."""
        client, id1, id2 = populated_client
        response = client.get("/api/v1/datasets")
        data = response.json()
        for item in data:
            assert "dataset_id" in item
            assert "name" in item
            assert "row_count" in item
            assert "created_at" in item

    def test_list_store_unavailable_returns_500(self, tmp_path):
        """Test that store unavailability returns 500."""
        from unittest.mock import MagicMock

        broken_service = MagicMock(spec=DatasetService)
        broken_service.list_all.side_effect = OSError("Storage unavailable")

        app.dependency_overrides[get_dataset_service] = lambda: broken_service
        with TestClient(app) as c:
            response = c.get("/api/v1/datasets")
            assert response.status_code == 500
            assert "unavailable" in response.json()["detail"].lower()
        app.dependency_overrides.clear()


class TestGetDatasetDetail:
    """Tests for GET /api/v1/datasets/{datasetId}."""

    def test_get_existing_dataset(self, populated_client):
        """Test that an existing dataset returns 200 with full detail."""
        client, id1, id2 = populated_client
        response = client.get(f"/api/v1/datasets/{id1}")
        assert response.status_code == 200
        data = response.json()
        assert data["dataset_id"] == id1
        assert data["name"] == "users.csv"
        assert data["row_count"] == 2
        assert data["column_count"] == 2
        assert data["source_type"] == "csv"
        assert "created_at" in data

    def test_get_nonexistent_dataset_returns_404(self, client):
        """Test that a valid UUID that doesn't exist returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/datasets/{fake_id}")
        assert response.status_code == 404

    def test_get_invalid_id_format_returns_422(self, client):
        """Test that an invalid dataset_id format returns 422."""
        response = client.get("/api/v1/datasets/not-a-valid-uuid")
        assert response.status_code == 422
        assert "invalid" in response.json()["detail"].lower()

    def test_get_detail_contains_all_fields(self, populated_client):
        """Test that the detail response contains all required fields."""
        client, id1, id2 = populated_client
        response = client.get(f"/api/v1/datasets/{id2}")
        assert response.status_code == 200
        data = response.json()
        required_fields = ["dataset_id", "name", "row_count", "column_count", "created_at", "source_type"]
        for field in required_fields:
            assert field in data


class TestDeleteDataset:
    """Tests for DELETE /api/v1/datasets/{datasetId}."""

    def test_delete_existing_dataset_returns_204(self, populated_client):
        """Test that deleting an existing dataset returns 204 with no body."""
        client, id1, id2 = populated_client
        response = client.delete(f"/api/v1/datasets/{id1}")
        assert response.status_code == 204
        assert response.content == b""

    def test_delete_removes_from_list(self, populated_client):
        """Test that a deleted dataset no longer appears in list."""
        client, id1, id2 = populated_client
        client.delete(f"/api/v1/datasets/{id1}")
        response = client.get("/api/v1/datasets")
        ids = [item["dataset_id"] for item in response.json()]
        assert id1 not in ids

    def test_delete_nonexistent_dataset_returns_404(self, client):
        """Test that deleting a non-existent dataset returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.delete(f"/api/v1/datasets/{fake_id}")
        assert response.status_code == 404

    def test_delete_invalid_id_format_returns_400(self, client):
        """Test that a malformed dataset_id returns 400."""
        response = client.delete("/api/v1/datasets/not-valid-uuid")
        assert response.status_code == 400
        assert "malformed" in response.json()["detail"].lower()

    def test_deleted_dataset_returns_404_on_detail(self, populated_client):
        """Test that a deleted dataset returns 404 on subsequent detail requests."""
        client, id1, id2 = populated_client
        client.delete(f"/api/v1/datasets/{id1}")
        response = client.get(f"/api/v1/datasets/{id1}")
        assert response.status_code == 404
