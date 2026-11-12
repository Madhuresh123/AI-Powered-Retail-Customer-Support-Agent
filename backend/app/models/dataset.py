"""Dataset metadata model and related enums."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class SourceType(str, Enum):
    """Enum representing the source of a dataset."""

    CSV = "csv"
    API = "api"


class DatasetMetadata(BaseModel):
    """Metadata for a stored dataset."""

    dataset_id: str  # UUID v4
    name: str  # Original filename or derived name
    row_count: int  # Total number of data rows
    column_count: int  # Total number of columns
    source_type: SourceType  # "csv" or "api"
    source_url: str | None = None  # Only for API imports
    created_at: datetime  # ISO 8601 timestamp
    file_size_bytes: int  # Size of stored Parquet file
