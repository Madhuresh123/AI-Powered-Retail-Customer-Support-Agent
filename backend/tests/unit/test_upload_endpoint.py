"""Unit tests for the CSV upload endpoint."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_csv_parser, get_dataset_service
from app.main import app
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


class TestUploadCSV:
    """Tests for POST /api/v1/datasets/upload."""

    def test_successful_upload(self, client):
        """Test that a valid CSV upload returns 201 with correct metadata."""
        csv_content = b"name,age,city\nAlice,30,NYC\nBob,25,LA\n"
        response = client.post(
            "/api/v1/datasets/upload",
            files={"file": ("test_data.csv", csv_content, "text/csv")},
        )
        assert response.status_code == 201
        data = response.json()
        assert "dataset_id" in data
        assert data["name"] == "test_data.csv"
        assert data["row_count"] == 2

    def test_upload_no_file_returns_422(self, client):
        """Test that a request with no file returns 422."""
        response = client.post("/api/v1/datasets/upload")
        assert response.status_code == 422

    def test_upload_invalid_csv_returns_400(self, client):
        """Test that an invalid CSV (bad encoding) returns 400."""
        invalid_content = b"\xff\xfe\x00\x01"
        response = client.post(
            "/api/v1/datasets/upload",
            files={"file": ("bad.csv", invalid_content, "text/csv")},
        )
        assert response.status_code == 400

    def test_upload_empty_csv_returns_400(self, client):
        """Test that a CSV with header but no data rows returns 400."""
        csv_content = b"col1,col2,col3\n"
        response = client.post(
            "/api/v1/datasets/upload",
            files={"file": ("empty.csv", csv_content, "text/csv")},
        )
        assert response.status_code == 400

    def test_upload_returns_valid_uuid(self, client):
        """Test that the returned dataset_id is a valid UUID v4."""
        csv_content = b"x,y\n1,2\n"
        response = client.post(
            "/api/v1/datasets/upload",
            files={"file": ("data.csv", csv_content, "text/csv")},
        )
        assert response.status_code == 201
        dataset_id = response.json()["dataset_id"]
        # Should not raise
        uuid.UUID(dataset_id, version=4)

    def test_upload_preserves_filename(self, client):
        """Test that the response name matches the uploaded filename."""
        csv_content = b"a,b\n1,2\n"
        response = client.post(
            "/api/v1/datasets/upload",
            files={"file": ("my_report.csv", csv_content, "text/csv")},
        )
        assert response.status_code == 201
        assert response.json()["name"] == "my_report.csv"

    def test_upload_correct_row_count(self, client):
        """Test that row_count matches the actual number of data rows."""
        csv_content = b"h1,h2\nr1c1,r1c2\nr2c1,r2c2\nr3c1,r3c2\n"
        response = client.post(
            "/api/v1/datasets/upload",
            files={"file": ("rows.csv", csv_content, "text/csv")},
        )
        assert response.status_code == 201
        assert response.json()["row_count"] == 3
