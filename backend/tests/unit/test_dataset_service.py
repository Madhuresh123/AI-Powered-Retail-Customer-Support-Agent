"""Unit tests for the DatasetService class."""

import tempfile
from datetime import datetime, timezone

import pandas as pd
import pytest

from app.exceptions import DatasetNotFoundError
from app.models.dataset import DatasetMetadata, SourceType
from app.services.dataset_service import DatasetService


@pytest.fixture
def tmp_storage(tmp_path):
    """Provide a temporary storage directory for tests."""
    return str(tmp_path / "datasets")


@pytest.fixture
def service(tmp_storage):
    """Create a DatasetService with a temporary storage path."""
    return DatasetService(storage_path=tmp_storage)


@pytest.fixture
def sample_df():
    """Create a sample DataFrame for testing."""
    return pd.DataFrame({
        "name": ["Alice", "Bob", "Charlie"],
        "age": [30, 25, 35],
        "city": ["New York", "London", "Paris"],
    })


@pytest.fixture
def sample_metadata():
    """Create sample metadata for testing."""
    return DatasetMetadata(
        dataset_id="",  # Will be overwritten by store()
        name="test_data.csv",
        row_count=3,
        column_count=3,
        source_type=SourceType.CSV,
        source_url=None,
        created_at=datetime.now(timezone.utc),
        file_size_bytes=0,  # Will be updated by store()
    )


class TestStore:
    """Tests for the store() method."""

    def test_store_returns_uuid(self, service, sample_df, sample_metadata):
        """Store should return a valid UUID v4 string."""
        dataset_id = service.store(sample_df, sample_metadata)
        # UUID v4 format: 8-4-4-4-12 hex characters
        import uuid
        parsed = uuid.UUID(dataset_id, version=4)
        assert str(parsed) == dataset_id

    def test_store_writes_parquet_file(self, service, sample_df, sample_metadata, tmp_storage):
        """Store should write a Parquet file to the storage directory."""
        from pathlib import Path
        dataset_id = service.store(sample_df, sample_metadata)
        parquet_path = Path(tmp_storage) / f"{dataset_id}.parquet"
        assert parquet_path.exists()

    def test_store_updates_metadata_index(self, service, sample_df, sample_metadata):
        """Store should add an entry to the metadata index."""
        dataset_id = service.store(sample_df, sample_metadata)
        metadata = service.get_metadata(dataset_id)
        assert metadata.dataset_id == dataset_id
        assert metadata.name == "test_data.csv"
        assert metadata.row_count == 3
        assert metadata.column_count == 3

    def test_store_updates_file_size(self, service, sample_df, sample_metadata):
        """Store should set file_size_bytes to the actual Parquet file size."""
        dataset_id = service.store(sample_df, sample_metadata)
        metadata = service.get_metadata(dataset_id)
        assert metadata.file_size_bytes > 0


class TestGetDataframe:
    """Tests for the get_dataframe() method."""

    def test_get_dataframe_returns_stored_data(self, service, sample_df, sample_metadata):
        """get_dataframe should return the same data that was stored."""
        dataset_id = service.store(sample_df, sample_metadata)
        result = service.get_dataframe(dataset_id)
        pd.testing.assert_frame_equal(result, sample_df)

    def test_get_dataframe_raises_not_found(self, service):
        """get_dataframe should raise DatasetNotFoundError for non-existent id."""
        with pytest.raises(DatasetNotFoundError):
            service.get_dataframe("non-existent-id")


class TestGetMetadata:
    """Tests for the get_metadata() method."""

    def test_get_metadata_returns_correct_entry(self, service, sample_df, sample_metadata):
        """get_metadata should return the correct metadata for a stored dataset."""
        dataset_id = service.store(sample_df, sample_metadata)
        metadata = service.get_metadata(dataset_id)
        assert metadata.dataset_id == dataset_id
        assert metadata.name == "test_data.csv"
        assert metadata.source_type == SourceType.CSV

    def test_get_metadata_raises_not_found(self, service):
        """get_metadata should raise DatasetNotFoundError for non-existent id."""
        with pytest.raises(DatasetNotFoundError):
            service.get_metadata("non-existent-id")


class TestListAll:
    """Tests for the list_all() method."""

    def test_list_all_empty_store(self, service):
        """list_all should return empty list when no datasets exist."""
        result = service.list_all()
        assert result == []

    def test_list_all_returns_all_datasets(self, service, sample_df):
        """list_all should return all stored datasets."""
        for i in range(3):
            meta = DatasetMetadata(
                dataset_id="",
                name=f"dataset_{i}.csv",
                row_count=3,
                column_count=3,
                source_type=SourceType.CSV,
                created_at=datetime.now(timezone.utc),
                file_size_bytes=0,
            )
            service.store(sample_df, meta)

        result = service.list_all()
        assert len(result) == 3

    def test_list_all_ordered_by_created_at_descending(self, service, sample_df):
        """list_all should return datasets ordered by created_at descending."""
        from datetime import timedelta

        base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        for i in range(3):
            meta = DatasetMetadata(
                dataset_id="",
                name=f"dataset_{i}.csv",
                row_count=3,
                column_count=3,
                source_type=SourceType.CSV,
                created_at=base_time + timedelta(days=i),
                file_size_bytes=0,
            )
            service.store(sample_df, meta)

        result = service.list_all()
        timestamps = [d.created_at for d in result]
        assert timestamps == sorted(timestamps, reverse=True)


class TestDelete:
    """Tests for the delete() method."""

    def test_delete_removes_parquet_file(self, service, sample_df, sample_metadata, tmp_storage):
        """delete should remove the Parquet file from storage."""
        from pathlib import Path
        dataset_id = service.store(sample_df, sample_metadata)
        parquet_path = Path(tmp_storage) / f"{dataset_id}.parquet"
        assert parquet_path.exists()

        service.delete(dataset_id)
        assert not parquet_path.exists()

    def test_delete_removes_metadata_entry(self, service, sample_df, sample_metadata):
        """delete should remove the dataset from the metadata index."""
        dataset_id = service.store(sample_df, sample_metadata)
        service.delete(dataset_id)
        assert not service.exists(dataset_id)

    def test_delete_raises_not_found(self, service):
        """delete should raise DatasetNotFoundError for non-existent id."""
        with pytest.raises(DatasetNotFoundError):
            service.delete("non-existent-id")

    def test_delete_not_in_list(self, service, sample_df, sample_metadata):
        """After deletion, dataset should not appear in list_all results."""
        dataset_id = service.store(sample_df, sample_metadata)
        service.delete(dataset_id)
        all_datasets = service.list_all()
        ids = [d.dataset_id for d in all_datasets]
        assert dataset_id not in ids


class TestExists:
    """Tests for the exists() method."""

    def test_exists_returns_true_for_stored_dataset(self, service, sample_df, sample_metadata):
        """exists should return True for a dataset that has been stored."""
        dataset_id = service.store(sample_df, sample_metadata)
        assert service.exists(dataset_id) is True

    def test_exists_returns_false_for_non_existent(self, service):
        """exists should return False for a non-existent dataset_id."""
        assert service.exists("non-existent-id") is False

    def test_exists_returns_false_after_deletion(self, service, sample_df, sample_metadata):
        """exists should return False after a dataset has been deleted."""
        dataset_id = service.store(sample_df, sample_metadata)
        service.delete(dataset_id)
        assert service.exists(dataset_id) is False
