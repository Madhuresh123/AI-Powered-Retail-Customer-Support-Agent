"""Preview engine for generating data previews, column metadata, and statistical summaries."""

import pandas as pd

from app.models.schemas import ColumnDescriptor, PreviewResponse, SummaryResponse
from app.services.dataset_service import DatasetService


class PreviewEngine:
    """Generates data previews, column metadata, and statistical summaries."""

    PREVIEW_ROW_LIMIT = 20

    def __init__(self, dataset_service: DatasetService):
        self.dataset_service = dataset_service

    def get_preview(self, dataset_id: str) -> PreviewResponse:
        """
        Return first min(R, 20) rows with column headers.

        Args:
            dataset_id: The UUID of the dataset to preview.

        Returns:
            PreviewResponse with columns (in original order), rows as list of dicts
            keyed by column name, and row_count indicating how many rows are returned.

        Raises:
            DatasetNotFoundError: If the dataset_id does not exist.
        """
        import io
        import pyarrow.parquet as pq

        if not self.dataset_service.exists(dataset_id):
            from app.exceptions import DatasetNotFoundError
            raise DatasetNotFoundError(dataset_id)

        # Get Parquet data - works with both file-based and Postgres services
        if hasattr(self.dataset_service, '_get_parquet_path'):
            # File-based service - read from file path
            parquet_path = self.dataset_service._get_parquet_path(dataset_id)
            pf = pq.ParquetFile(parquet_path)
        elif hasattr(self.dataset_service, 'get_parquet_bytes'):
            # Postgres service - read from bytes
            parquet_bytes = self.dataset_service.get_parquet_bytes(dataset_id)
            pf = pq.ParquetFile(io.BytesIO(parquet_bytes))
        else:
            # Fallback - load full DataFrame
            df = self.dataset_service.get_dataframe(dataset_id)
            columns = list(df.columns)
            preview_df = df.head(self.PREVIEW_ROW_LIMIT).fillna("")
            rows = [{col: str(row[col]) if row[col] != "" else "" for col in columns} for _, row in preview_df.iterrows()]
            return PreviewResponse(columns=columns, rows=rows, row_count=len(rows))

        # Read only first batch (up to 20 rows)
        first_batch = next(pf.iter_batches(batch_size=self.PREVIEW_ROW_LIMIT))
        df = first_batch.to_pandas()

        columns = list(df.columns)
        preview_df = df.head(self.PREVIEW_ROW_LIMIT)
        preview_df = preview_df.fillna("")
        rows = []
        for _, row in preview_df.iterrows():
            row_dict = {col: str(row[col]) if row[col] != "" else "" for col in columns}
            rows.append(row_dict)

        return PreviewResponse(
            columns=columns,
            rows=rows,
            row_count=len(rows),
        )

    def get_columns(self, dataset_id: str) -> list[ColumnDescriptor]:
        """
        Return column names and inferred types in original order.

        Args:
            dataset_id: The UUID of the dataset.

        Returns:
            List of ColumnDescriptor objects preserving column order.

        Raises:
            DatasetNotFoundError: If the dataset_id does not exist.
        """
        import io
        import pyarrow.parquet as pq

        if not self.dataset_service.exists(dataset_id):
            from app.exceptions import DatasetNotFoundError
            raise DatasetNotFoundError(dataset_id)

        # Get Parquet data - works with both file-based and Postgres services
        if hasattr(self.dataset_service, '_get_parquet_path'):
            parquet_path = self.dataset_service._get_parquet_path(dataset_id)
            pf = pq.ParquetFile(parquet_path)
        elif hasattr(self.dataset_service, 'get_parquet_bytes'):
            parquet_bytes = self.dataset_service.get_parquet_bytes(dataset_id)
            pf = pq.ParquetFile(io.BytesIO(parquet_bytes))
        else:
            df = self.dataset_service.get_dataframe(dataset_id)
            return [ColumnDescriptor(name=col, dtype=self.infer_column_type(df[col])) for col in df.columns]

        # Read first batch of 1000 rows for type inference
        first_batch = next(pf.iter_batches(batch_size=1000))
        df = first_batch.to_pandas()

        descriptors = []
        for col in df.columns:
            dtype = self.infer_column_type(df[col])
            descriptors.append(ColumnDescriptor(name=col, dtype=dtype))
        return descriptors

    def get_summary(self, dataset_id: str) -> SummaryResponse:
        """
        Compute statistical summary for the dataset.

        Args:
            dataset_id: The UUID of the dataset.

        Returns:
            SummaryResponse with row_count, column_count, missing_value_count,
            duplicate_row_count, and memory_usage_bytes.

        Raises:
            DatasetNotFoundError: If the dataset_id does not exist.
        """
        metadata = self.dataset_service.get_metadata(dataset_id)
        df = self.dataset_service.get_dataframe(dataset_id)

        row_count = len(df)
        column_count = len(df.columns)

        # Missing value count: cells that are null or empty string
        missing_value_count = int(df.isna().sum().sum())
        # Count empty strings for object/string columns
        for col in df.columns:
            if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
                missing_value_count += int((df[col] == "").sum())

        # Duplicate row count: skip for very large datasets (> 50K rows) to avoid timeout
        if row_count > 50000:
            duplicate_row_count = 0  # Skip expensive duplicate check
        elif row_count > 0:
            duplicate_row_count = int(df.duplicated(keep="first").sum())
        else:
            duplicate_row_count = 0

        # Memory usage: stored Parquet file size
        memory_usage_bytes = metadata.file_size_bytes

        return SummaryResponse(
            row_count=row_count,
            column_count=column_count,
            missing_value_count=missing_value_count,
            duplicate_row_count=duplicate_row_count,
            memory_usage_bytes=memory_usage_bytes,
        )

    def infer_column_type(self, series: pd.Series) -> str:
        """
        Infer column type as one of: "number", "string", "boolean", "date".

        Attempts numeric, boolean, then date parsing. Defaults to "string"
        for mixed or unrecognizable values.

        Args:
            series: A pandas Series representing a column of data.

        Returns:
            One of "number", "string", "boolean", "date".
        """
        # Drop null values for type inference
        non_null = series.dropna()

        # If all values are null/empty, default to string
        if len(non_null) == 0:
            return "string"

        # Filter out empty strings for type inference
        if non_null.dtype == object or pd.api.types.is_string_dtype(non_null):
            non_empty = non_null[non_null != ""]
            if len(non_empty) == 0:
                return "string"
        else:
            non_empty = non_null

        # Check if already boolean dtype (must check before numeric since bool is subtype of int)
        if pd.api.types.is_bool_dtype(series):
            return "boolean"

        # Check if already numeric dtype
        if pd.api.types.is_numeric_dtype(series):
            return "number"

        # For object columns, attempt type inference
        # Try boolean detection
        if self._is_boolean_column(non_empty):
            return "boolean"

        # Try numeric parsing
        if self._is_numeric_column(non_empty):
            return "number"

        # Try date parsing
        if self._is_date_column(non_empty):
            return "date"

        # Default to string
        return "string"

    def _is_boolean_column(self, series: pd.Series) -> bool:
        """Check if all non-empty values represent booleans."""
        boolean_values = {"true", "false", "0", "1", "yes", "no"}
        try:
            return all(
                str(val).strip().lower() in boolean_values for val in series
            )
        except (TypeError, ValueError):
            return False

    def _is_numeric_column(self, series: pd.Series) -> bool:
        """Check if all non-empty values can be parsed as numbers."""
        try:
            converted = pd.to_numeric(series, errors="coerce")
            # If all values were successfully converted (no NaN introduced)
            return not converted.isna().any()
        except (TypeError, ValueError):
            return False

    def _is_date_column(self, series: pd.Series) -> bool:
        """Check if all non-empty values can be parsed as dates."""
        try:
            converted = pd.to_datetime(series, errors="coerce", format="mixed")
            # If all values were successfully converted (no NaT introduced)
            return not converted.isna().any()
        except (TypeError, ValueError, OverflowError):
            return False
