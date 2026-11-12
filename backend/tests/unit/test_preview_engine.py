"""Unit tests for the PreviewEngine class."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from app.models.dataset import DatasetMetadata, SourceType
from app.services.dataset_service import DatasetService
from app.services.preview_engine import PreviewEngine
from app.exceptions import DatasetNotFoundError
from datetime import datetime


@pytest.fixture
def temp_storage(tmp_path):
    """Create a temporary storage directory for tests."""
    return str(tmp_path)


@pytest.fixture
def dataset_service(temp_storage):
    """Create a DatasetService instance with temporary storage."""
    return DatasetService(storage_path=temp_storage)


@pytest.fixture
def preview_engine(dataset_service):
    """Create a PreviewEngine instance."""
    return PreviewEngine(dataset_service=dataset_service)


def _store_dataset(dataset_service: DatasetService, df: pd.DataFrame, name: str = "test.csv") -> str:
    """Helper to store a dataset and return the dataset_id."""
    metadata = DatasetMetadata(
        dataset_id="",
        name=name,
        row_count=len(df),
        column_count=len(df.columns),
        source_type=SourceType.CSV,
        created_at=datetime.now(),
        file_size_bytes=0,
    )
    return dataset_service.store(df, metadata)


class TestGetPreview:
    """Tests for PreviewEngine.get_preview()."""

    def test_returns_all_rows_when_under_limit(self, preview_engine, dataset_service):
        """Preview returns all rows when dataset has fewer than 20 rows."""
        df = pd.DataFrame({"name": ["Alice", "Bob", "Charlie"], "age": ["30", "25", "35"]})
        dataset_id = _store_dataset(dataset_service, df)

        result = preview_engine.get_preview(dataset_id)

        assert result.row_count == 3
        assert result.columns == ["name", "age"]
        assert len(result.rows) == 3
        assert result.rows[0] == {"name": "Alice", "age": "30"}
        assert result.rows[1] == {"name": "Bob", "age": "25"}
        assert result.rows[2] == {"name": "Charlie", "age": "35"}

    def test_limits_to_20_rows(self, preview_engine, dataset_service):
        """Preview returns at most 20 rows for large datasets."""
        df = pd.DataFrame({"value": [str(i) for i in range(50)]})
        dataset_id = _store_dataset(dataset_service, df)

        result = preview_engine.get_preview(dataset_id)

        assert result.row_count == 20
        assert len(result.rows) == 20
        assert result.rows[0] == {"value": "0"}
        assert result.rows[19] == {"value": "19"}

    def test_empty_dataset_returns_columns_only(self, preview_engine, dataset_service):
        """Preview of empty dataset returns column headers with empty rows array."""
        df = pd.DataFrame(columns=["col_a", "col_b", "col_c"])
        dataset_id = _store_dataset(dataset_service, df)

        result = preview_engine.get_preview(dataset_id)

        assert result.row_count == 0
        assert result.columns == ["col_a", "col_b", "col_c"]
        assert result.rows == []

    def test_preserves_column_order(self, preview_engine, dataset_service):
        """Preview preserves original column ordering."""
        df = pd.DataFrame({"zebra": ["z"], "apple": ["a"], "mango": ["m"]})
        dataset_id = _store_dataset(dataset_service, df)

        result = preview_engine.get_preview(dataset_id)

        assert result.columns == ["zebra", "apple", "mango"]

    def test_rows_are_keyed_by_column_name(self, preview_engine, dataset_service):
        """Each row is a dict keyed by column name."""
        df = pd.DataFrame({"x": ["1"], "y": ["2"]})
        dataset_id = _store_dataset(dataset_service, df)

        result = preview_engine.get_preview(dataset_id)

        assert "x" in result.rows[0]
        assert "y" in result.rows[0]
        assert result.rows[0]["x"] == "1"
        assert result.rows[0]["y"] == "2"

    def test_raises_for_nonexistent_dataset(self, preview_engine):
        """Preview raises DatasetNotFoundError for unknown dataset_id."""
        with pytest.raises(DatasetNotFoundError):
            preview_engine.get_preview("nonexistent-uuid")


class TestGetColumns:
    """Tests for PreviewEngine.get_columns()."""

    def test_returns_column_descriptors_in_order(self, preview_engine, dataset_service):
        """Columns are returned in original order."""
        df = pd.DataFrame({"b_col": ["hello"], "a_col": ["42"], "c_col": ["true"]})
        dataset_id = _store_dataset(dataset_service, df)

        result = preview_engine.get_columns(dataset_id)

        assert len(result) == 3
        assert result[0].name == "b_col"
        assert result[1].name == "a_col"
        assert result[2].name == "c_col"

    def test_infers_numeric_type(self, preview_engine, dataset_service):
        """Numeric columns are detected."""
        df = pd.DataFrame({"numbers": ["1", "2.5", "3", "-4"]})
        dataset_id = _store_dataset(dataset_service, df)

        result = preview_engine.get_columns(dataset_id)

        assert result[0].dtype == "number"

    def test_infers_boolean_type(self, preview_engine, dataset_service):
        """Boolean columns are detected."""
        df = pd.DataFrame({"flags": ["true", "false", "True", "False"]})
        dataset_id = _store_dataset(dataset_service, df)

        result = preview_engine.get_columns(dataset_id)

        assert result[0].dtype == "boolean"

    def test_infers_date_type(self, preview_engine, dataset_service):
        """Date columns are detected."""
        df = pd.DataFrame({"dates": ["2024-01-01", "2024-06-15", "2023-12-31"]})
        dataset_id = _store_dataset(dataset_service, df)

        result = preview_engine.get_columns(dataset_id)

        assert result[0].dtype == "date"

    def test_defaults_to_string_for_mixed(self, preview_engine, dataset_service):
        """Mixed-type columns default to string."""
        df = pd.DataFrame({"mixed": ["hello", "42", "true", "2024-01-01"]})
        dataset_id = _store_dataset(dataset_service, df)

        result = preview_engine.get_columns(dataset_id)

        assert result[0].dtype == "string"

    def test_valid_dtype_values(self, preview_engine, dataset_service):
        """All inferred dtypes are one of the valid types."""
        df = pd.DataFrame({
            "text": ["hello", "world"],
            "num": ["1", "2"],
            "bool": ["true", "false"],
            "date": ["2024-01-01", "2024-02-01"],
        })
        dataset_id = _store_dataset(dataset_service, df)

        result = preview_engine.get_columns(dataset_id)

        valid_types = {"number", "string", "boolean", "date"}
        for col in result:
            assert col.dtype in valid_types

    def test_raises_for_nonexistent_dataset(self, preview_engine):
        """Columns raises DatasetNotFoundError for unknown dataset_id."""
        with pytest.raises(DatasetNotFoundError):
            preview_engine.get_columns("nonexistent-uuid")


class TestGetSummary:
    """Tests for PreviewEngine.get_summary()."""

    def test_basic_summary(self, preview_engine, dataset_service):
        """Summary returns correct counts for a simple dataset."""
        df = pd.DataFrame({"a": ["1", "2", "3"], "b": ["x", "y", "z"]})
        dataset_id = _store_dataset(dataset_service, df)

        result = preview_engine.get_summary(dataset_id)

        assert result.row_count == 3
        assert result.column_count == 2
        assert result.missing_value_count == 0
        assert result.duplicate_row_count == 0
        assert result.memory_usage_bytes > 0

    def test_counts_missing_nulls(self, preview_engine, dataset_service):
        """Summary counts null cells as missing values."""
        df = pd.DataFrame({"a": ["1", None, "3"], "b": [None, "y", None]})
        dataset_id = _store_dataset(dataset_service, df)

        result = preview_engine.get_summary(dataset_id)

        assert result.missing_value_count == 3

    def test_counts_missing_empty_strings(self, preview_engine, dataset_service):
        """Summary counts empty string cells as missing values."""
        df = pd.DataFrame({"a": ["1", "", "3"], "b": ["", "y", ""]})
        dataset_id = _store_dataset(dataset_service, df)

        result = preview_engine.get_summary(dataset_id)

        assert result.missing_value_count == 3

    def test_counts_duplicate_rows(self, preview_engine, dataset_service):
        """Summary counts rows that are exact duplicates of another row."""
        df = pd.DataFrame({
            "a": ["1", "2", "1", "1"],
            "b": ["x", "y", "x", "x"],
        })
        dataset_id = _store_dataset(dataset_service, df)

        result = preview_engine.get_summary(dataset_id)

        # Rows 2 and 3 are duplicates of row 0
        assert result.duplicate_row_count == 2

    def test_empty_dataset_summary(self, preview_engine, dataset_service):
        """Summary for empty dataset has zeroes for counts."""
        df = pd.DataFrame(columns=["col_a", "col_b"])
        dataset_id = _store_dataset(dataset_service, df)

        result = preview_engine.get_summary(dataset_id)

        assert result.row_count == 0
        assert result.column_count == 2
        assert result.missing_value_count == 0
        assert result.duplicate_row_count == 0
        assert result.memory_usage_bytes > 0

    def test_memory_usage_reflects_file_size(self, preview_engine, dataset_service):
        """Memory usage equals the stored Parquet file size."""
        df = pd.DataFrame({"data": ["a" * 100] * 50})
        dataset_id = _store_dataset(dataset_service, df)

        result = preview_engine.get_summary(dataset_id)
        metadata = dataset_service.get_metadata(dataset_id)

        assert result.memory_usage_bytes == metadata.file_size_bytes

    def test_raises_for_nonexistent_dataset(self, preview_engine):
        """Summary raises DatasetNotFoundError for unknown dataset_id."""
        with pytest.raises(DatasetNotFoundError):
            preview_engine.get_summary("nonexistent-uuid")


class TestInferColumnType:
    """Tests for PreviewEngine.infer_column_type()."""

    def test_integer_column(self, preview_engine):
        """Integer values are inferred as number."""
        series = pd.Series(["1", "2", "3", "100"])
        assert preview_engine.infer_column_type(series) == "number"

    def test_float_column(self, preview_engine):
        """Float values are inferred as number."""
        series = pd.Series(["1.5", "2.7", "3.14"])
        assert preview_engine.infer_column_type(series) == "number"

    def test_negative_numbers(self, preview_engine):
        """Negative numbers are inferred as number."""
        series = pd.Series(["-1", "0", "1", "-2.5"])
        assert preview_engine.infer_column_type(series) == "number"

    def test_boolean_true_false(self, preview_engine):
        """true/false strings are inferred as boolean."""
        series = pd.Series(["true", "false", "True", "FALSE"])
        assert preview_engine.infer_column_type(series) == "boolean"

    def test_boolean_yes_no(self, preview_engine):
        """yes/no strings are inferred as boolean."""
        series = pd.Series(["yes", "no", "Yes", "NO"])
        assert preview_engine.infer_column_type(series) == "boolean"

    def test_boolean_zero_one(self, preview_engine):
        """0/1 strings are inferred as boolean (not number since boolean check runs first)."""
        series = pd.Series(["0", "1", "0", "1"])
        assert preview_engine.infer_column_type(series) == "boolean"

    def test_date_iso_format(self, preview_engine):
        """ISO date strings are inferred as date."""
        series = pd.Series(["2024-01-01", "2024-06-15", "2023-12-31"])
        assert preview_engine.infer_column_type(series) == "date"

    def test_mixed_values_default_to_string(self, preview_engine):
        """Mixed types default to string."""
        series = pd.Series(["hello", "42", "true", "2024-01-01"])
        assert preview_engine.infer_column_type(series) == "string"

    def test_text_values(self, preview_engine):
        """Plain text defaults to string."""
        series = pd.Series(["hello", "world", "foo", "bar"])
        assert preview_engine.infer_column_type(series) == "string"

    def test_all_null_defaults_to_string(self, preview_engine):
        """All-null column defaults to string."""
        series = pd.Series([None, None, None])
        assert preview_engine.infer_column_type(series) == "string"

    def test_all_empty_strings_defaults_to_string(self, preview_engine):
        """All empty string column defaults to string."""
        series = pd.Series(["", "", ""])
        assert preview_engine.infer_column_type(series) == "string"

    def test_numeric_pandas_dtype(self, preview_engine):
        """Numeric pandas dtype is directly inferred as number."""
        series = pd.Series([1, 2, 3, 4])
        assert preview_engine.infer_column_type(series) == "number"

    def test_boolean_pandas_dtype(self, preview_engine):
        """Boolean pandas dtype is directly inferred as boolean."""
        series = pd.Series([True, False, True])
        assert preview_engine.infer_column_type(series) == "boolean"
