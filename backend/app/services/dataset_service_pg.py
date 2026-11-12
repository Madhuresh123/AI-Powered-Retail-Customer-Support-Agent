"""Dataset service using Neon Postgres for storage."""

import io
import uuid
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy.orm import Session

from app.database import DatasetRecord, get_session_factory
from app.exceptions import DatasetNotFoundError
from app.models.dataset import DatasetMetadata, SourceType


class DatasetServicePG:
    """Manages dataset persistence using Neon Postgres.

    Stores both metadata and Parquet binary data in the database,
    eliminating the need for local file storage.
    """

    def __init__(self):
        self._session_factory = get_session_factory()

    def _get_session(self) -> Session:
        return self._session_factory()

    def store(self, df: pd.DataFrame, metadata: DatasetMetadata) -> str:
        """Store a DataFrame as Parquet in Postgres."""
        dataset_id = str(uuid.uuid4())
        metadata.dataset_id = dataset_id

        # Serialize DataFrame to Parquet bytes
        buffer = io.BytesIO()
        df.to_parquet(buffer, index=False)
        parquet_bytes = buffer.getvalue()

        metadata.file_size_bytes = len(parquet_bytes)

        record = DatasetRecord(
            dataset_id=dataset_id,
            name=metadata.name,
            row_count=metadata.row_count,
            column_count=metadata.column_count,
            source_type=metadata.source_type.value,
            source_url=metadata.source_url,
            created_at=metadata.created_at,
            file_size_bytes=metadata.file_size_bytes,
            parquet_data=parquet_bytes,
        )

        with self._get_session() as session:
            session.add(record)
            session.commit()

        return dataset_id

    def get_dataframe(self, dataset_id: str) -> pd.DataFrame:
        """Load and return the DataFrame for a dataset."""
        with self._get_session() as session:
            record = session.get(DatasetRecord, dataset_id)
            if not record:
                raise DatasetNotFoundError(dataset_id)
            buffer = io.BytesIO(record.parquet_data)
            return pd.read_parquet(buffer)

    def get_metadata(self, dataset_id: str) -> DatasetMetadata:
        """Return metadata for a specific dataset."""
        with self._get_session() as session:
            record = session.get(DatasetRecord, dataset_id)
            if not record:
                raise DatasetNotFoundError(dataset_id)
            return DatasetMetadata(
                dataset_id=record.dataset_id,
                name=record.name,
                row_count=record.row_count,
                column_count=record.column_count,
                source_type=SourceType(record.source_type),
                source_url=record.source_url,
                created_at=record.created_at,
                file_size_bytes=record.file_size_bytes,
            )

    def list_all(self) -> list[DatasetMetadata]:
        """Return all dataset metadata, ordered by created_at descending."""
        with self._get_session() as session:
            records = (
                session.query(DatasetRecord)
                .order_by(DatasetRecord.created_at.desc())
                .all()
            )
            return [
                DatasetMetadata(
                    dataset_id=r.dataset_id,
                    name=r.name,
                    row_count=r.row_count,
                    column_count=r.column_count,
                    source_type=SourceType(r.source_type),
                    source_url=r.source_url,
                    created_at=r.created_at,
                    file_size_bytes=r.file_size_bytes,
                )
                for r in records
            ]

    def delete(self, dataset_id: str) -> None:
        """Remove a dataset."""
        with self._get_session() as session:
            record = session.get(DatasetRecord, dataset_id)
            if not record:
                raise DatasetNotFoundError(dataset_id)
            session.delete(record)
            session.commit()

    def exists(self, dataset_id: str) -> bool:
        """Check if a dataset exists."""
        with self._get_session() as session:
            record = session.get(DatasetRecord, dataset_id)
            return record is not None

    def get_parquet_bytes(self, dataset_id: str) -> bytes:
        """Get raw Parquet bytes for a dataset (used by preview engine)."""
        with self._get_session() as session:
            record = session.get(DatasetRecord, dataset_id)
            if not record:
                raise DatasetNotFoundError(dataset_id)
            return record.parquet_data
