"""Tests for the POST /api/v1/datasets/import-api endpoint."""

from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_dataset_service, get_rest_importer
from app.main import app
from app.services.dataset_service import DatasetService
from app.services.rest_importer import ImportResult, RESTImporter


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


class TestImportAPI:
    """Tests for POST /api/v1/datasets/import-api endpoint."""

    def test_successful_import(self, client):
        """Successful import returns 201 with dataset_id, source_url, and row_count."""
        test_df = pd.DataFrame(
            {"name": ["Alice", "Bob"], "age": [30, 25]}
        )
        mock_result = ImportResult(
            dataframe=test_df,
            source_url="https://api.example.com/data",
            row_count=2,
        )

        mock_importer = RESTImporter()
        mock_importer.import_from_url = AsyncMock(return_value=mock_result)
        app.dependency_overrides[get_rest_importer] = lambda: mock_importer

        response = client.post(
            "/api/v1/datasets/import-api",
            json={"url": "https://api.example.com/data"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "dataset_id" in data
        assert data["source_url"] == "https://api.example.com/data"
        assert data["row_count"] == 2

        # Clean up override
        del app.dependency_overrides[get_rest_importer]

    def test_import_invalid_url_returns_422(self, client):
        """Invalid URL returns 422."""
        from app.exceptions import InvalidURLError

        mock_importer = RESTImporter()
        mock_importer.import_from_url = AsyncMock(
            side_effect=InvalidURLError(url="not-a-url", reason="Invalid URL")
        )
        app.dependency_overrides[get_rest_importer] = lambda: mock_importer

        response = client.post(
            "/api/v1/datasets/import-api",
            json={"url": "not-a-url"},
        )

        assert response.status_code == 422
        assert "detail" in response.json()

        del app.dependency_overrides[get_rest_importer]

    def test_import_upstream_error_returns_502(self, client):
        """Upstream error returns 502."""
        from app.exceptions import UpstreamError

        mock_importer = RESTImporter()
        mock_importer.import_from_url = AsyncMock(
            side_effect=UpstreamError(reason="Request timed out after 30 seconds")
        )
        app.dependency_overrides[get_rest_importer] = lambda: mock_importer

        response = client.post(
            "/api/v1/datasets/import-api",
            json={"url": "https://unreachable.example.com/data"},
        )

        assert response.status_code == 502
        assert "detail" in response.json()

        del app.dependency_overrides[get_rest_importer]

    def test_import_payload_too_large_returns_413(self, client):
        """Payload too large returns 413."""
        from app.exceptions import PayloadTooLargeError

        mock_importer = RESTImporter()
        mock_importer.import_from_url = AsyncMock(
            side_effect=PayloadTooLargeError(
                size_bytes=60 * 1024 * 1024, max_bytes=50 * 1024 * 1024
            )
        )
        app.dependency_overrides[get_rest_importer] = lambda: mock_importer

        response = client.post(
            "/api/v1/datasets/import-api",
            json={"url": "https://big-data.example.com/large"},
        )

        assert response.status_code == 413
        assert "detail" in response.json()

        del app.dependency_overrides[get_rest_importer]

    def test_import_unsupported_format_returns_422(self, client):
        """Unsupported JSON format returns 422."""
        from app.exceptions import UnsupportedFormatError

        mock_importer = RESTImporter()
        mock_importer.import_from_url = AsyncMock(
            side_effect=UnsupportedFormatError(
                reason="Expected a JSON array at the top level"
            )
        )
        app.dependency_overrides[get_rest_importer] = lambda: mock_importer

        response = client.post(
            "/api/v1/datasets/import-api",
            json={"url": "https://api.example.com/not-array"},
        )

        assert response.status_code == 422
        assert "detail" in response.json()

        del app.dependency_overrides[get_rest_importer]

    def test_import_missing_url_returns_422(self, client):
        """Missing url field returns 422 validation error."""
        response = client.post(
            "/api/v1/datasets/import-api",
            json={},
        )

        assert response.status_code == 422

    def test_import_empty_body_returns_422(self, client):
        """Empty request body returns 422."""
        response = client.post(
            "/api/v1/datasets/import-api",
            content="",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422
