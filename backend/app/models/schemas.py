"""API request and response schemas for the Data Insight API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.dataset import SourceType


class UploadResponse(BaseModel):
    """Response schema for successful CSV upload."""

    dataset_id: str
    name: str
    row_count: int


class ImportRequest(BaseModel):
    """Request schema for REST API import."""

    url: str


class ImportResponse(BaseModel):
    """Response schema for successful REST API import."""

    dataset_id: str
    source_url: str
    row_count: int


class DatasetListItem(BaseModel):
    """Schema for a dataset item in the list response."""

    dataset_id: str
    name: str
    row_count: int
    created_at: datetime


class DatasetDetail(BaseModel):
    """Schema for full dataset detail response."""

    dataset_id: str
    name: str
    row_count: int
    column_count: int
    created_at: datetime
    source_type: SourceType


class PreviewResponse(BaseModel):
    """Response schema for dataset preview."""

    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int


class ColumnDescriptor(BaseModel):
    """Schema for a single column descriptor."""

    name: str
    dtype: str  # "number", "string", "boolean", "date"


class SummaryResponse(BaseModel):
    """Response schema for dataset statistical summary."""

    row_count: int
    column_count: int
    missing_value_count: int
    duplicate_row_count: int
    memory_usage_bytes: int


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    detail: str
