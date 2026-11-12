"""Unit tests for AnalyticsEngine.execute_query pipeline and serialization."""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from app.models.analytics_schemas import (
    AggregationFunction,
    AggregationOp,
    FilterExpression,
    FilterOperator,
    QueryRequest,
    SortDirection,
    SortSpec,
)
from app.services.analytics_engine import AnalyticsEngine


@pytest.fixture
def engine():
    return AnalyticsEngine()


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
        "age": [30, 25, 35, 28, 22],
        "score": [85.5, 90.0, 78.3, 92.1, 88.7],
        "active": [True, False, True, True, False],
    })


class TestExecuteQueryPipeline:
    """Test that execute_query applies operations in the correct order."""

    def test_basic_no_operations(self, engine, sample_df):
        """When no operations are specified, returns first page of all data."""
        query = QueryRequest()
        result = engine.execute_query(sample_df, query)

        assert result.columns == ["name", "age", "score", "active"]
        assert len(result.rows) == 5
        assert result.pagination.total_rows == 5
        assert result.pagination.current_page == 1
        assert result.pagination.page_size == 50

    def test_filter_then_paginate(self, engine, sample_df):
        """Filters reduce total_rows, pagination reflects the filtered count."""
        query = QueryRequest(
            filters=[FilterExpression(column="age", operator=FilterOperator.GT, value=25)],
            page=1,
            page_size=2,
        )
        result = engine.execute_query(sample_df, query)

        # age > 25: Alice(30), Charlie(35), Diana(28) = 3 rows
        assert result.pagination.total_rows == 3
        assert result.pagination.total_pages == 2
        assert len(result.rows) == 2

    def test_search_then_paginate(self, engine, sample_df):
        """Search reduces results before pagination is applied."""
        query = QueryRequest(
            search="ali",
            page=1,
            page_size=50,
        )
        result = engine.execute_query(sample_df, query)

        # Only "Alice" matches "ali" (case-insensitive)
        assert result.pagination.total_rows == 1
        assert len(result.rows) == 1
        assert result.rows[0]["name"] == "Alice"

    def test_aggregation_with_group_by(self, engine, sample_df):
        """Aggregation with group_by produces correct column ordering."""
        query = QueryRequest(
            aggregations=[AggregationOp(function=AggregationFunction.AVG, column="age")],
            group_by=["active"],
        )
        result = engine.execute_query(sample_df, query)

        # Columns should be group_by columns first, then aggregated columns
        assert result.columns[0] == "active"
        assert "avg_age" in result.columns

    def test_sort_applied_after_aggregation(self, engine, sample_df):
        """Sort is applied to the aggregated result."""
        query = QueryRequest(
            aggregations=[AggregationOp(function=AggregationFunction.COUNT, column="name")],
            group_by=["active"],
            sort=[SortSpec(column="count_name", direction=SortDirection.DESC)],
        )
        result = engine.execute_query(sample_df, query)

        # active=True has 3 (Alice, Charlie, Diana), active=False has 2 (Bob, Eve)
        assert result.rows[0]["count_name"] >= result.rows[1]["count_name"]

    def test_full_pipeline_filter_search_sort_paginate(self, engine):
        """Full pipeline: filter → search → sort → paginate."""
        df = pd.DataFrame({
            "name": ["Alice Smith", "Bob Jones", "Alice Brown", "Charlie Alice", "Diana"],
            "age": [30, 25, 35, 28, 22],
        })
        query = QueryRequest(
            filters=[FilterExpression(column="age", operator=FilterOperator.GTE, value=25)],
            search="alice",
            sort=[SortSpec(column="age", direction=SortDirection.ASC)],
            page=1,
            page_size=2,
        )
        result = engine.execute_query(df, query)

        # Filter: age >= 25 → Alice Smith(30), Bob Jones(25), Alice Brown(35), Charlie Alice(28)
        # Search "alice": Alice Smith(30), Alice Brown(35), Charlie Alice(28)
        # Sort by age asc: Charlie Alice(28), Alice Smith(30), Alice Brown(35)
        # Paginate page 1, size 2: Charlie Alice(28), Alice Smith(30)
        assert result.pagination.total_rows == 3
        assert len(result.rows) == 2
        assert result.rows[0]["name"] == "Charlie Alice"
        assert result.rows[1]["name"] == "Alice Smith"


class TestSerializeValue:
    """Test _serialize_value for proper type handling."""

    def test_none_value(self, engine):
        assert engine._serialize_value(None) is None

    def test_nan_value(self, engine):
        assert engine._serialize_value(float("nan")) is None

    def test_numpy_nan(self, engine):
        assert engine._serialize_value(np.nan) is None

    def test_string_value(self, engine):
        assert engine._serialize_value("hello") == "hello"

    def test_string_numeric_not_coerced(self, engine):
        """String '123' should remain a string, not be coerced to a number."""
        assert engine._serialize_value("123") == "123"
        assert isinstance(engine._serialize_value("123"), str)

    def test_integer(self, engine):
        assert engine._serialize_value(42) == 42
        assert isinstance(engine._serialize_value(42), int)

    def test_numpy_integer(self, engine):
        val = np.int64(42)
        assert engine._serialize_value(val) == 42
        assert isinstance(engine._serialize_value(val), int)

    def test_float(self, engine):
        assert engine._serialize_value(3.14) == 3.14
        assert isinstance(engine._serialize_value(3.14), float)

    def test_numpy_float(self, engine):
        val = np.float64(3.14)
        result = engine._serialize_value(val)
        assert abs(result - 3.14) < 1e-10
        assert isinstance(result, float)

    def test_boolean_true(self, engine):
        assert engine._serialize_value(True) is True
        assert isinstance(engine._serialize_value(True), bool)

    def test_boolean_false(self, engine):
        assert engine._serialize_value(False) is False
        assert isinstance(engine._serialize_value(False), bool)

    def test_boolean_not_coerced_to_int(self, engine):
        """Boolean True should not be returned as int 1."""
        result = engine._serialize_value(True)
        assert result is True
        assert not isinstance(result, int) or isinstance(result, bool)

    def test_pandas_timestamp(self, engine):
        ts = pd.Timestamp("2024-01-15 10:30:00")
        result = engine._serialize_value(ts)
        assert "2024-01-15" in result
        assert isinstance(result, str)

    def test_datetime_object(self, engine):
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = engine._serialize_value(dt)
        assert "2024-01-15" in result
        assert isinstance(result, str)

    def test_pandas_nat(self, engine):
        """pd.NaT should be serialized as None."""
        assert engine._serialize_value(pd.NaT) is None


class TestSerializeRows:
    """Test _serialize_rows for full DataFrame serialization."""

    def test_basic_serialization(self, engine):
        df = pd.DataFrame({
            "name": ["Alice", "Bob"],
            "age": [30, 25],
        })
        rows = engine._serialize_rows(df)
        assert len(rows) == 2
        assert rows[0] == {"name": "Alice", "age": 30}
        assert rows[1] == {"name": "Bob", "age": 25}

    def test_null_handling(self, engine):
        df = pd.DataFrame({
            "name": ["Alice", None],
            "age": [30, None],
        })
        rows = engine._serialize_rows(df)
        assert rows[1]["name"] is None
        assert rows[1]["age"] is None

    def test_mixed_types(self, engine):
        df = pd.DataFrame({
            "name": ["Alice"],
            "age": [30],
            "score": [85.5],
            "active": [True],
        })
        rows = engine._serialize_rows(df)
        assert isinstance(rows[0]["name"], str)
        assert isinstance(rows[0]["age"], int)
        assert isinstance(rows[0]["score"], float)
        assert isinstance(rows[0]["active"], bool)

    def test_datetime_column(self, engine):
        df = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-15", "2024-06-30"]),
        })
        rows = engine._serialize_rows(df)
        assert "2024-01-15" in rows[0]["date"]
        assert "2024-06-30" in rows[1]["date"]

    def test_empty_dataframe(self, engine):
        df = pd.DataFrame({"col": pd.Series([], dtype="object")})
        rows = engine._serialize_rows(df)
        assert rows == []


class TestColumnOrdering:
    """Test that column ordering is preserved correctly."""

    def test_no_aggregation_preserves_order(self, engine):
        df = pd.DataFrame({
            "z_col": [1, 2],
            "a_col": [3, 4],
            "m_col": [5, 6],
        })
        query = QueryRequest()
        result = engine.execute_query(df, query)
        assert result.columns == ["z_col", "a_col", "m_col"]

    def test_aggregation_group_by_first(self, engine):
        df = pd.DataFrame({
            "category": ["A", "B", "A", "B"],
            "value": [10, 20, 30, 40],
        })
        query = QueryRequest(
            aggregations=[AggregationOp(function=AggregationFunction.SUM, column="value")],
            group_by=["category"],
        )
        result = engine.execute_query(df, query)
        # group_by columns first, then aggregated columns
        assert result.columns[0] == "category"
        assert result.columns[1] == "sum_value"
