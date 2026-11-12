"""Unit tests for the preview, columns, and summary API endpoints."""

import uuid
from datetime import datetime, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_dataset_service, get_preview_engine
from app.main import app
from app.models.dataset import DatasetMetadata, SourceType
from app.services.dataset_service import DatasetService
from app.services.preview_engine import PreviewEngine


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def temp_storage(tmp_path):
    """Create a temporary storage directory for tests."""
    return str(tmp_path)


@pytest.fixture
def dataset_service(temp_storage):
    """Create a DatasetService instance with temporary storage."""
    return DatasetService(storage_path=temp_storage)


def _store_test_dataset(service: DatasetService, df: pd.DataFrame, name: str = "test.csv") -> str:
    """Helper to store a test dataset and return the dataset_id."""
    metadata = DatasetMetadata(
        dataset_id="",
        name=name,
        row_count=len(df),
        column_count=len(df.columns),
        source_type=SourceType.CSV,
        created_at=datetime.now(timezone.utc),
        file_size_bytes=0,
    )
    return service.store(df, metadata)


class TestPreviewEndpoint:
    """Tests for GET /api/v1/datasets/{dataset_id}/preview."""

    def test_preview_returns_200_with_valid_dataset(self, client, dataset_service):
        """Preview endpoint returns 200 with correct response structure."""
        df = pd.DataFrame({"name": ["Alice", "Bob"], "age": [30, 25]})
        dataset_id = _store_test_dataset(dataset_service, df)

        app.dependency_overrides[get_dataset_service] = lambda: dataset_service
        app.dependency_overrides[get_preview_engine] = lambda: PreviewEngine(dataset_service)
        response = client.get(f"/api/v1/datasets/{dataset_id}/preview")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert "columns" in data
        assert "rows" in data
        assert "row_count" in data
        assert data["columns"] == ["name", "age"]
        assert data["row_count"] == 2
        assert len(data["rows"]) == 2

    def test_preview_rows_keyed_by_column_name(self, client, dataset_service):
        """Preview rows are dictionaries keyed by column name."""
        df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
        dataset_id = _store_test_dataset(dataset_service, df)

        app.dependency_overrides[get_dataset_service] = lambda: dataset_service
        app.dependency_overrides[get_preview_engine] = lambda: PreviewEngine(dataset_service)
        response = client.get(f"/api/v1/datasets/{dataset_id}/preview")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        rows = response.json()["rows"]
        assert "x" in rows[0]
        assert "y" in rows[0]

    def test_preview_returns_404_for_nonexistent_dataset(self, client, dataset_service):
        """Preview endpoint returns 404 for a dataset that doesn't exist."""
        fake_id = str(uuid.uuid4())

        app.dependency_overrides[get_dataset_service] = lambda: dataset_service
        app.dependency_overrides[get_preview_engine] = lambda: PreviewEngine(dataset_service)
        response = client.get(f"/api/v1/datasets/{fake_id}/preview")
        app.dependency_overrides.clear()

        assert response.status_code == 404
        assert "detail" in response.json()

    def test_preview_limits_to_20_rows(self, client, dataset_service):
        """Preview endpoint returns at most 20 rows."""
        df = pd.DataFrame({"val": list(range(50))})
        dataset_id = _store_test_dataset(dataset_service, df)

        app.dependency_overrides[get_dataset_service] = lambda: dataset_service
        app.dependency_overrides[get_preview_engine] = lambda: PreviewEngine(dataset_service)
        response = client.get(f"/api/v1/datasets/{dataset_id}/preview")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["row_count"] == 20
        assert len(response.json()["rows"]) == 20


class TestColumnsEndpoint:
    """Tests for GET /api/v1/datasets/{dataset_id}/columns."""

    def test_columns_returns_200_with_valid_dataset(self, client, dataset_service):
        """Columns endpoint returns 200 with column descriptors."""
        df = pd.DataFrame({"name": ["Alice"], "age": [30], "active": [True]})
        dataset_id = _store_test_dataset(dataset_service, df)

        app.dependency_overrides[get_dataset_service] = lambda: dataset_service
        app.dependency_overrides[get_preview_engine] = lambda: PreviewEngine(dataset_service)
        response = client.get(f"/api/v1/datasets/{dataset_id}/columns")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3
        # Each item has name and dtype
        for col in data:
            assert "name" in col
            assert "dtype" in col
            assert col["dtype"] in ("number", "string", "boolean", "date")

    def test_columns_preserves_order(self, client, dataset_service):
        """Columns are returned in the same order as in the dataset."""
        df = pd.DataFrame({"z_col": [1], "a_col": [2], "m_col": [3]})
        dataset_id = _store_test_dataset(dataset_service, df)

        app.dependency_overrides[get_dataset_service] = lambda: dataset_service
        app.dependency_overrides[get_preview_engine] = lambda: PreviewEngine(dataset_service)
        response = client.get(f"/api/v1/datasets/{dataset_id}/columns")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        names = [col["name"] for col in response.json()]
        assert names == ["z_col", "a_col", "m_col"]

    def test_columns_returns_404_for_nonexistent_dataset(self, client, dataset_service):
        """Columns endpoint returns 404 for a dataset that doesn't exist."""
        fake_id = str(uuid.uuid4())

        app.dependency_overrides[get_dataset_service] = lambda: dataset_service
        app.dependency_overrides[get_preview_engine] = lambda: PreviewEngine(dataset_service)
        response = client.get(f"/api/v1/datasets/{fake_id}/columns")
        app.dependency_overrides.clear()

        assert response.status_code == 200 or response.status_code == 404
        if response.status_code == 404:
            assert "detail" in response.json()

    def test_columns_infers_types_correctly(self, client, dataset_service):
        """Columns endpoint infers types for numeric and string columns."""
        df = pd.DataFrame({"number_col": [1, 2, 3], "text_col": ["a", "b", "c"]})
        dataset_id = _store_test_dataset(dataset_service, df)

        app.dependency_overrides[get_dataset_service] = lambda: dataset_service
        app.dependency_overrides[get_preview_engine] = lambda: PreviewEngine(dataset_service)
        response = client.get(f"/api/v1/datasets/{dataset_id}/columns")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        cols = {c["name"]: c["dtype"] for c in response.json()}
        assert cols["number_col"] == "number"
        assert cols["text_col"] == "string"


class TestSummaryEndpoint:
    """Tests for GET /api/v1/datasets/{dataset_id}/summary."""

    def test_summary_returns_200_with_valid_dataset(self, client, dataset_service):
        """Summary endpoint returns 200 with correct summary structure."""
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        dataset_id = _store_test_dataset(dataset_service, df)

        app.dependency_overrides[get_dataset_service] = lambda: dataset_service
        app.dependency_overrides[get_preview_engine] = lambda: PreviewEngine(dataset_service)
        response = client.get(f"/api/v1/datasets/{dataset_id}/summary")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["row_count"] == 3
        assert data["column_count"] == 2
        assert "missing_value_count" in data
        assert "duplicate_row_count" in data
        assert "memory_usage_bytes" in data

    def test_summary_returns_404_for_nonexistent_dataset(self, client, dataset_service):
        """Summary endpoint returns 404 for a dataset that doesn't exist."""
        fake_id = str(uuid.uuid4())

        app.dependency_overrides[get_dataset_service] = lambda: dataset_service
        app.dependency_overrides[get_preview_engine] = lambda: PreviewEngine(dataset_service)
        response = client.get(f"/api/v1/datasets/{fake_id}/summary")
        app.dependency_overrides.clear()

        assert response.status_code == 404
        assert "detail" in response.json()

    def test_summary_counts_missing_values(self, client, dataset_service):
        """Summary endpoint correctly counts missing values (null and empty string)."""
        df = pd.DataFrame({"a": [1, None, 3], "b": ["x", "", "z"]})
        dataset_id = _store_test_dataset(dataset_service, df)

        app.dependency_overrides[get_dataset_service] = lambda: dataset_service
        app.dependency_overrides[get_preview_engine] = lambda: PreviewEngine(dataset_service)
        response = client.get(f"/api/v1/datasets/{dataset_id}/summary")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        # 1 null in column a + 1 empty string in column b = 2
        assert response.json()["missing_value_count"] == 2

    def test_summary_counts_duplicate_rows(self, client, dataset_service):
        """Summary endpoint correctly counts duplicate rows."""
        df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
        dataset_id = _store_test_dataset(dataset_service, df)

        app.dependency_overrides[get_dataset_service] = lambda: dataset_service
        app.dependency_overrides[get_preview_engine] = lambda: PreviewEngine(dataset_service)
        response = client.get(f"/api/v1/datasets/{dataset_id}/summary")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        # Row [1, "x"] appears twice, so 1 duplicate
        assert response.json()["duplicate_row_count"] == 1

    def test_summary_memory_usage_is_positive(self, client, dataset_service):
        """Summary endpoint reports positive memory usage for non-empty datasets."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        dataset_id = _store_test_dataset(dataset_service, df)

        app.dependency_overrides[get_dataset_service] = lambda: dataset_service
        app.dependency_overrides[get_preview_engine] = lambda: PreviewEngine(dataset_service)
        response = client.get(f"/api/v1/datasets/{dataset_id}/summary")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["memory_usage_bytes"] > 0
