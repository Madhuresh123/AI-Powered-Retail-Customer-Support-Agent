"""Dataset service for managing dataset persistence."""

import json
import uuid
from pathlib import Path

import pandas as pd

from app.exceptions import DatasetNotFoundError
from app.models.dataset import DatasetMetadata


class DatasetService:
    """Manages dataset persistence — storing, retrieving, listing, and deleting datasets."""

    def __init__(self, storage_path: str = "/data/datasets"):
        self.storage_path = Path(storage_path)
        self.metadata_path = self.storage_path / "metadata.json"
        self._ensure_storage_exists()

    def _ensure_storage_exists(self) -> None:
        """Create the storage directory and metadata file if they don't exist."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        if not self.metadata_path.exists():
            self._write_metadata_index({"datasets": {}})

    def _read_metadata_index(self) -> dict:
        """Read the metadata.json index file."""
        with open(self.metadata_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_metadata_index(self, data: dict) -> None:
        """Write the metadata.json index file."""
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _get_parquet_path(self, dataset_id: str) -> Path:
        """Get the Parquet file path for a dataset."""
        return self.storage_path / f"{dataset_id}.parquet"

    def store(self, df: pd.DataFrame, metadata: DatasetMetadata) -> str:
        """
        Store a DataFrame as Parquet and update the metadata index.

        Args:
            df: The DataFrame to store.
            metadata: The metadata for the dataset. The dataset_id field will be
                      overwritten with a newly generated UUID v4.

        Returns:
            The generated dataset_id (UUID v4).
        """
        dataset_id = str(uuid.uuid4())
        metadata.dataset_id = dataset_id

        # Write DataFrame to Parquet
        parquet_path = self._get_parquet_path(dataset_id)
        df.to_parquet(parquet_path, index=False)

        # Update file_size_bytes with actual Parquet file size
        metadata.file_size_bytes = parquet_path.stat().st_size

        # Update metadata index
        index = self._read_metadata_index()
        index["datasets"][dataset_id] = metadata.model_dump(mode="json")
        self._write_metadata_index(index)

        return dataset_id

    def get_dataframe(self, dataset_id: str) -> pd.DataFrame:
        """
        Load and return the DataFrame for a dataset.

        Args:
            dataset_id: The UUID of the dataset to retrieve.

        Returns:
            The dataset as a pandas DataFrame.

        Raises:
            DatasetNotFoundError: If the dataset_id does not exist.
        """
        if not self.exists(dataset_id):
            raise DatasetNotFoundError(dataset_id)

        parquet_path = self._get_parquet_path(dataset_id)
        return pd.read_parquet(parquet_path)

    def get_metadata(self, dataset_id: str) -> DatasetMetadata:
        """
        Return metadata for a specific dataset.

        Args:
            dataset_id: The UUID of the dataset.

        Returns:
            The DatasetMetadata for the specified dataset.

        Raises:
            DatasetNotFoundError: If the dataset_id does not exist in the index.
        """
        index = self._read_metadata_index()
        if dataset_id not in index["datasets"]:
            raise DatasetNotFoundError(dataset_id)

        return DatasetMetadata(**index["datasets"][dataset_id])

    def list_all(self) -> list[DatasetMetadata]:
        """
        Return all dataset metadata, ordered by created_at descending.

        Returns:
            A list of DatasetMetadata objects sorted by creation time (most recent first).
        """
        index = self._read_metadata_index()
        datasets = [
            DatasetMetadata(**entry)
            for entry in index["datasets"].values()
        ]
        datasets.sort(key=lambda d: d.created_at, reverse=True)
        return datasets

    def delete(self, dataset_id: str) -> None:
        """
        Remove a dataset's Parquet file and metadata entry.

        Args:
            dataset_id: The UUID of the dataset to delete.

        Raises:
            DatasetNotFoundError: If the dataset_id does not exist.
        """
        index = self._read_metadata_index()
        if dataset_id not in index["datasets"]:
            raise DatasetNotFoundError(dataset_id)

        # Remove Parquet file
        parquet_path = self._get_parquet_path(dataset_id)
        if parquet_path.exists():
            parquet_path.unlink()

        # Remove from metadata index
        del index["datasets"][dataset_id]
        self._write_metadata_index(index)

    def exists(self, dataset_id: str) -> bool:
        """
        Check if a dataset exists in the metadata index.

        Args:
            dataset_id: The UUID of the dataset to check.

        Returns:
            True if the dataset exists, False otherwise.
        """
        index = self._read_metadata_index()
        return dataset_id in index["datasets"]
