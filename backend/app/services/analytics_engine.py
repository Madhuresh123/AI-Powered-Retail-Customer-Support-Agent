"""Analytics Engine service for query processing on DataFrames."""

import math
from datetime import datetime

import numpy as np
import pandas as pd

from app.exceptions import AnalyticsValidationError
from app.models.analytics_schemas import (
    AggregationFunction,
    AggregationOp,
    FilterExpression,
    FilterOperator,
    PaginationMeta,
    QueryRequest,
    QueryResponse,
    SortDirection,
    SortSpec,
)


class AnalyticsEngine:
    """Core query processing service for dataset analytics.

    Applies filtering, searching, aggregation, sorting, and pagination
    operations on pandas DataFrames.
    """

    def apply_filters(
        self, df: pd.DataFrame, filters: list[FilterExpression] | None
    ) -> pd.DataFrame:
        """Apply all filter expressions to DataFrame using logical AND.

        Args:
            df: The input DataFrame to filter.
            filters: List of filter expressions to apply. If None or empty,
                returns the DataFrame unchanged.

        Returns:
            Filtered DataFrame containing only rows that satisfy all conditions.

        Raises:
            AnalyticsValidationError: If a column doesn't exist, type is incompatible,
                or between operator has invalid value format.
        """
        if filters is None or len(filters) == 0:
            return df

        result = df

        for filt in filters:
            col = filt.column
            op = filt.operator
            value = filt.value

            # Validate column existence
            if col not in result.columns:
                raise AnalyticsValidationError(
                    f"Column '{col}' does not exist in dataset"
                )

            # Validate type compatibility for numeric-only operators
            numeric_only_ops = {
                FilterOperator.GT,
                FilterOperator.GTE,
                FilterOperator.LT,
                FilterOperator.LTE,
                FilterOperator.BETWEEN,
            }
            if op in numeric_only_ops and not pd.api.types.is_numeric_dtype(
                result[col]
            ):
                raise AnalyticsValidationError(
                    f"Column '{col}' is not numeric; cannot apply '{op.value}'"
                )

            # Validate type compatibility for string-only operators
            string_only_ops = {
                FilterOperator.CONTAINS,
                FilterOperator.STARTS_WITH,
                FilterOperator.ENDS_WITH,
                FilterOperator.IN,
            }
            if op in string_only_ops and pd.api.types.is_numeric_dtype(result[col]):
                raise AnalyticsValidationError(
                    f"Column '{col}' is numeric; cannot apply string operator '{op.value}'"
                )

            # Validate between operator value format
            if op == FilterOperator.BETWEEN:
                if not isinstance(value, (list, tuple)) or len(value) != 2:
                    raise AnalyticsValidationError(
                        "between operator requires [min, max] where min <= max"
                    )
                if value[0] > value[1]:
                    raise AnalyticsValidationError(
                        "between operator requires [min, max] where min <= max"
                    )

            # Validate 'in' operator value format
            if op == FilterOperator.IN:
                if not isinstance(value, (list, tuple)):
                    raise AnalyticsValidationError(
                        "in operator requires a list of values"
                    )
                if len(value) > 100:
                    raise AnalyticsValidationError(
                        "in operator supports up to 100 items"
                    )

            # Handle null exclusion logic:
            # Exclude rows with null in the filtered column UNLESS filter is eq with None
            if op == FilterOperator.EQ and value is None:
                # Special case: eq with null — return rows where column IS null
                mask = result[col].isna()
            else:
                # Exclude nulls first, then apply the filter
                not_null_mask = result[col].notna()

                # Apply the specific operator
                if op == FilterOperator.EQ:
                    mask = not_null_mask & (result[col] == value)
                elif op == FilterOperator.NEQ:
                    mask = not_null_mask & (result[col] != value)
                elif op == FilterOperator.GT:
                    mask = not_null_mask & (result[col] > value)
                elif op == FilterOperator.GTE:
                    mask = not_null_mask & (result[col] >= value)
                elif op == FilterOperator.LT:
                    mask = not_null_mask & (result[col] < value)
                elif op == FilterOperator.LTE:
                    mask = not_null_mask & (result[col] <= value)
                elif op == FilterOperator.BETWEEN:
                    mask = not_null_mask & (
                        (result[col] >= value[0]) & (result[col] <= value[1])
                    )
                elif op == FilterOperator.CONTAINS:
                    mask = not_null_mask & (
                        result[col]
                        .astype(str)
                        .str.contains(str(value), case=False, na=False)
                    )
                elif op == FilterOperator.STARTS_WITH:
                    mask = not_null_mask & (
                        result[col]
                        .astype(str)
                        .str.lower()
                        .str.startswith(str(value).lower())
                    )
                elif op == FilterOperator.ENDS_WITH:
                    mask = not_null_mask & (
                        result[col]
                        .astype(str)
                        .str.lower()
                        .str.endswith(str(value).lower())
                    )
                elif op == FilterOperator.IN:
                    # Case-sensitive exact match
                    mask = not_null_mask & (result[col].isin(value))
                else:
                    raise AnalyticsValidationError(
                        f"Unsupported filter operator: '{op.value}'"
                    )

            result = result[mask]

        return result.reset_index(drop=True)

    def apply_search(
        self,
        df: pd.DataFrame,
        search: str | None,
        search_columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """Case-insensitive substring search across specified or all columns.

        Args:
            df: The input DataFrame to search.
            search: The search term for case-insensitive substring matching.
                If None or empty string, returns df unchanged.
            search_columns: Optional list of columns to restrict the search to.
                If None, searches all columns.

        Returns:
            DataFrame containing only rows where at least one searched column
            contains the search term as a case-insensitive substring.

        Raises:
            AnalyticsValidationError: If a column in search_columns does not
                exist in the DataFrame.
        """
        if search is None or search == "":
            return df

        # Validate search_columns if provided
        if search_columns is not None:
            for col in search_columns:
                if col not in df.columns:
                    raise AnalyticsValidationError(
                        f"Column '{col}' does not exist in dataset"
                    )

        # Determine which columns to search
        columns_to_search = search_columns if search_columns is not None else list(df.columns)

        # Build a boolean mask: True if any searched column contains the term
        search_lower = search.lower()
        mask = pd.Series([False] * len(df), index=df.index)

        for col in columns_to_search:
            mask = mask | df[col].astype(str).str.lower().str.contains(
                search_lower, na=False, regex=False
            )

        result = df[mask]
        return result.reset_index(drop=True)

    def apply_aggregations(
        self,
        df: pd.DataFrame,
        aggregations: list[AggregationOp] | None,
        group_by: list[str] | None = None,
    ) -> pd.DataFrame:
        """Compute aggregate values, optionally grouped by columns.

        Args:
            df: The input DataFrame to aggregate.
            aggregations: List of aggregation operations to apply. If None,
                returns the DataFrame unchanged.
            group_by: Optional list of columns to group by (up to 5).

        Returns:
            DataFrame with aggregated results. Without group_by, returns a
            single-row DataFrame. With group_by, returns one row per group.

        Raises:
            AnalyticsValidationError: If aggregations is empty list, column
                doesn't exist, or numeric function applied to non-numeric column.
        """
        if aggregations is None:
            return df

        if len(aggregations) == 0:
            raise AnalyticsValidationError(
                "At least one aggregation is required"
            )

        # Validate group_by columns exist
        if group_by is not None:
            for col in group_by:
                if col not in df.columns:
                    raise AnalyticsValidationError(
                        f"Column '{col}' does not exist in dataset"
                    )

        # Numeric-only aggregation functions
        numeric_only_funcs = {
            AggregationFunction.SUM,
            AggregationFunction.AVG,
            AggregationFunction.MEDIAN,
            AggregationFunction.STD,
        }

        # Mapping from AggregationFunction to pandas aggregation function name
        func_mapping = {
            AggregationFunction.COUNT: "count",
            AggregationFunction.SUM: "sum",
            AggregationFunction.AVG: "mean",
            AggregationFunction.MIN: "min",
            AggregationFunction.MAX: "max",
            AggregationFunction.MEDIAN: "median",
            AggregationFunction.STD: "std",
            AggregationFunction.DISTINCT_COUNT: "nunique",
        }

        # Validate each aggregation
        for agg in aggregations:
            if agg.column not in df.columns:
                raise AnalyticsValidationError(
                    f"Column '{agg.column}' does not exist in dataset"
                )
            if agg.function in numeric_only_funcs and not pd.api.types.is_numeric_dtype(
                df[agg.column]
            ):
                raise AnalyticsValidationError(
                    f"Cannot apply '{agg.function.value}' to non-numeric column '{agg.column}'"
                )

        # Build aggregation dictionary: {column: [list of pandas funcs]}
        # We need to handle multiple aggregations per column and naming
        if group_by is not None:
            grouped = df.groupby(group_by)
            agg_results = {}
            for agg in aggregations:
                output_col = f"{agg.function.value}_{agg.column}"
                pandas_func = func_mapping[agg.function]
                agg_results[output_col] = grouped[agg.column].agg(pandas_func)

            result = pd.DataFrame(agg_results)
            result = result.reset_index()
        else:
            agg_results = {}
            for agg in aggregations:
                output_col = f"{agg.function.value}_{agg.column}"
                pandas_func = func_mapping[agg.function]
                agg_results[output_col] = [df[agg.column].agg(pandas_func)]

            result = pd.DataFrame(agg_results)

        return result

    def apply_sort(
        self, df: pd.DataFrame, sort: list[SortSpec] | None
    ) -> pd.DataFrame:
        """Apply multi-column sorting to DataFrame.

        Args:
            df: The input DataFrame to sort.
            sort: List of sort specifications with column and direction.
                If None or empty, returns the DataFrame unchanged.

        Returns:
            Sorted DataFrame with null values appearing last regardless
            of sort direction. String columns use case-insensitive
            lexicographic ordering.

        Raises:
            AnalyticsValidationError: If sort list exceeds 10 entries,
                a column doesn't exist, or direction is invalid.
        """
        if sort is None or len(sort) == 0:
            return df

        # Validate max 10 sort columns
        if len(sort) > 10:
            raise AnalyticsValidationError(
                "Maximum of 10 sort columns allowed"
            )

        # Validate each sort column exists
        for spec in sort:
            if spec.column not in df.columns:
                raise AnalyticsValidationError(
                    f"Column '{spec.column}' does not exist in dataset"
                )

        # Build sort parameters
        sort_columns = []
        ascending = []
        temp_columns = []

        result = df.copy()

        for spec in sort:
            col = spec.column
            is_asc = spec.direction == SortDirection.ASC

            # For string columns, create a temporary lowercase column for
            # case-insensitive sorting
            if pd.api.types.is_string_dtype(result[col]) or pd.api.types.is_object_dtype(result[col]):
                temp_col = f"__sort_key_{col}"
                result[temp_col] = result[col].str.lower()
                sort_columns.append(temp_col)
                temp_columns.append(temp_col)
            else:
                sort_columns.append(col)

            ascending.append(is_asc)

        # Sort with null-last behavior
        result = result.sort_values(
            by=sort_columns,
            ascending=ascending,
            na_position="last",
        )

        # Drop temporary sort key columns
        if temp_columns:
            result = result.drop(columns=temp_columns)

        # Reset index before returning
        return result.reset_index(drop=True)

    def apply_pagination(
        self, df: pd.DataFrame, page: int, page_size: int
    ) -> tuple[pd.DataFrame, PaginationMeta]:
        """Offset-based pagination returning a page slice and metadata.

        Args:
            df: The input DataFrame to paginate.
            page: The page number (1-indexed, must be >= 1).
            page_size: The number of rows per page (must be between 1 and 1000).

        Returns:
            A tuple of (sliced DataFrame, PaginationMeta).

        Raises:
            AnalyticsValidationError: If page < 1 or page_size not in [1, 1000].
        """
        # Validate page
        if page < 1:
            raise AnalyticsValidationError("page must be a positive integer")

        # Validate page_size
        if page_size < 1 or page_size > 1000:
            raise AnalyticsValidationError(
                "page_size must be between 1 and 1000"
            )

        # Calculate pagination metadata
        total_rows = len(df)
        total_pages = math.ceil(total_rows / page_size) if total_rows > 0 else 0

        # Calculate offset slice
        start = (page - 1) * page_size
        end = page * page_size

        # Slice the DataFrame
        result = df.iloc[start:end]

        # Reset index before returning
        result = result.reset_index(drop=True)

        # Build pagination metadata
        pagination_meta = PaginationMeta(
            total_rows=total_rows,
            total_pages=total_pages,
            current_page=page,
            page_size=page_size,
        )

        return (result, pagination_meta)

    def _serialize_value(self, value):
        """Serialize a single DataFrame cell value for JSON output.

        Converts pandas/numpy types to native Python types suitable for
        JSON serialization.

        Args:
            value: The cell value to serialize.

        Returns:
            A JSON-compatible Python value (None, str, int, float, bool).
        """
        if pd.isna(value):
            return None
        if isinstance(value, (pd.Timestamp, datetime)):
            return value.isoformat()
        if isinstance(value, bool):  # must check before int since bool is subclass of int
            return value
        if isinstance(value, (int, np.integer)):
            return int(value)
        if isinstance(value, (float, np.floating)):
            return float(value)
        return str(value) if not isinstance(value, str) else value

    def _serialize_rows(self, df: pd.DataFrame) -> list[dict]:
        """Serialize all rows of a DataFrame into a list of dictionaries.

        Each row is converted to a dict mapping column names to serialized
        values using _serialize_value for type handling.

        Args:
            df: The DataFrame to serialize.

        Returns:
            A list of row dictionaries with properly typed values.
        """
        rows = []
        for _, row in df.iterrows():
            serialized = {}
            for col in df.columns:
                serialized[col] = self._serialize_value(row[col])
            rows.append(serialized)
        return rows

    def execute_query(self, df: pd.DataFrame, query: QueryRequest) -> QueryResponse:
        """Execute the full query pipeline: filter → search → aggregate → sort → paginate.

        Orchestrates all query operations in the fixed order defined by the
        Analytics Engine specification, then serializes the result DataFrame
        into a JSON-compatible response.

        Args:
            df: The input DataFrame to query.
            query: The QueryRequest containing all operation parameters.

        Returns:
            A QueryResponse with columns, serialized rows, and pagination metadata.

        Raises:
            AnalyticsValidationError: If any operation encounters invalid
                parameters (invalid columns, type mismatches, etc.).
        """
        # 1. Apply filters
        df = self.apply_filters(df, query.filters)

        # 2. Apply search
        df = self.apply_search(df, query.search, query.search_columns)

        # 3. Apply aggregations
        df = self.apply_aggregations(df, query.aggregations, query.group_by)

        # 4. Apply sort
        df = self.apply_sort(df, query.sort)

        # 5. Apply pagination
        df, pagination = self.apply_pagination(df, query.page, query.page_size)

        # 6. Get column ordering from the result DataFrame
        columns = list(df.columns)

        # 7. Serialize rows with proper type handling
        serialized_rows = self._serialize_rows(df)

        return QueryResponse(
            columns=columns,
            rows=serialized_rows,
            pagination=pagination,
        )
