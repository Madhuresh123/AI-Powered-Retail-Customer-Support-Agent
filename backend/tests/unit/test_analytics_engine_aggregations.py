"""Unit tests for AnalyticsEngine.apply_aggregations method."""

import numpy as np
import pandas as pd
import pytest

from app.exceptions import AnalyticsValidationError
from app.models.analytics_schemas import AggregationFunction, AggregationOp
from app.services.analytics_engine import AnalyticsEngine


@pytest.fixture
def engine():
    return AnalyticsEngine()


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        {
            "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
            "age": [30, 25, 35, 28, 32],
            "salary": [70000, 55000, 90000, 62000, 80000],
            "department": ["Engineering", "Marketing", "Engineering", "Marketing", "Engineering"],
        }
    )


class TestApplyAggregationsNone:
    """Test that None aggregations returns df unchanged."""

    def test_none_aggregations_returns_unchanged(self, engine, sample_df):
        result = engine.apply_aggregations(sample_df, None)
        pd.testing.assert_frame_equal(result, sample_df)

    def test_none_aggregations_with_group_by_returns_unchanged(self, engine, sample_df):
        result = engine.apply_aggregations(sample_df, None, group_by=["department"])
        pd.testing.assert_frame_equal(result, sample_df)


class TestApplyAggregationsValidation:
    """Test validation errors."""

    def test_empty_aggregations_raises_error(self, engine, sample_df):
        with pytest.raises(AnalyticsValidationError, match="At least one aggregation is required"):
            engine.apply_aggregations(sample_df, [])

    def test_nonexistent_column_raises_error(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.COUNT, column="nonexistent")
        with pytest.raises(AnalyticsValidationError, match="Column 'nonexistent' does not exist"):
            engine.apply_aggregations(sample_df, [agg])

    def test_numeric_func_on_string_column_raises_error(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.SUM, column="name")
        with pytest.raises(
            AnalyticsValidationError,
            match="Cannot apply 'sum' to non-numeric column 'name'",
        ):
            engine.apply_aggregations(sample_df, [agg])

    def test_avg_on_string_column_raises_error(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.AVG, column="department")
        with pytest.raises(
            AnalyticsValidationError,
            match="Cannot apply 'avg' to non-numeric column 'department'",
        ):
            engine.apply_aggregations(sample_df, [agg])

    def test_median_on_string_column_raises_error(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.MEDIAN, column="name")
        with pytest.raises(
            AnalyticsValidationError,
            match="Cannot apply 'median' to non-numeric column 'name'",
        ):
            engine.apply_aggregations(sample_df, [agg])

    def test_std_on_string_column_raises_error(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.STD, column="name")
        with pytest.raises(
            AnalyticsValidationError,
            match="Cannot apply 'std' to non-numeric column 'name'",
        ):
            engine.apply_aggregations(sample_df, [agg])

    def test_group_by_nonexistent_column_raises_error(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.COUNT, column="name")
        with pytest.raises(AnalyticsValidationError, match="Column 'nonexistent' does not exist"):
            engine.apply_aggregations(sample_df, [agg], group_by=["nonexistent"])


class TestApplyAggregationsWithoutGroupBy:
    """Test aggregations without group_by (single-row result)."""

    def test_count(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.COUNT, column="name")
        result = engine.apply_aggregations(sample_df, [agg])
        assert result.columns.tolist() == ["count_name"]
        assert result["count_name"].iloc[0] == 5

    def test_sum(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.SUM, column="salary")
        result = engine.apply_aggregations(sample_df, [agg])
        assert result.columns.tolist() == ["sum_salary"]
        assert result["sum_salary"].iloc[0] == 357000

    def test_avg(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.AVG, column="age")
        result = engine.apply_aggregations(sample_df, [agg])
        assert result.columns.tolist() == ["avg_age"]
        assert result["avg_age"].iloc[0] == 30.0

    def test_min(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.MIN, column="age")
        result = engine.apply_aggregations(sample_df, [agg])
        assert result.columns.tolist() == ["min_age"]
        assert result["min_age"].iloc[0] == 25

    def test_max(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.MAX, column="salary")
        result = engine.apply_aggregations(sample_df, [agg])
        assert result.columns.tolist() == ["max_salary"]
        assert result["max_salary"].iloc[0] == 90000

    def test_median(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.MEDIAN, column="age")
        result = engine.apply_aggregations(sample_df, [agg])
        assert result.columns.tolist() == ["median_age"]
        assert result["median_age"].iloc[0] == 30.0

    def test_std(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.STD, column="age")
        result = engine.apply_aggregations(sample_df, [agg])
        assert result.columns.tolist() == ["std_age"]
        expected_std = sample_df["age"].std()
        assert abs(result["std_age"].iloc[0] - expected_std) < 1e-10

    def test_distinct_count(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.DISTINCT_COUNT, column="department")
        result = engine.apply_aggregations(sample_df, [agg])
        assert result.columns.tolist() == ["distinct_count_department"]
        assert result["distinct_count_department"].iloc[0] == 2

    def test_multiple_aggregations(self, engine, sample_df):
        aggs = [
            AggregationOp(function=AggregationFunction.COUNT, column="name"),
            AggregationOp(function=AggregationFunction.AVG, column="salary"),
            AggregationOp(function=AggregationFunction.MAX, column="age"),
        ]
        result = engine.apply_aggregations(sample_df, aggs)
        assert result.columns.tolist() == ["count_name", "avg_salary", "max_age"]
        assert len(result) == 1
        assert result["count_name"].iloc[0] == 5
        assert result["avg_salary"].iloc[0] == 71400.0
        assert result["max_age"].iloc[0] == 35


class TestApplyAggregationsWithGroupBy:
    """Test aggregations with group_by."""

    def test_group_by_single_column(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.COUNT, column="name")
        result = engine.apply_aggregations(sample_df, [agg], group_by=["department"])
        assert "department" in result.columns
        assert "count_name" in result.columns
        # Engineering has 3, Marketing has 2
        eng_row = result[result["department"] == "Engineering"]
        mkt_row = result[result["department"] == "Marketing"]
        assert eng_row["count_name"].iloc[0] == 3
        assert mkt_row["count_name"].iloc[0] == 2

    def test_group_by_with_sum(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.SUM, column="salary")
        result = engine.apply_aggregations(sample_df, [agg], group_by=["department"])
        eng_row = result[result["department"] == "Engineering"]
        mkt_row = result[result["department"] == "Marketing"]
        assert eng_row["sum_salary"].iloc[0] == 240000  # 70000+90000+80000
        assert mkt_row["sum_salary"].iloc[0] == 117000  # 55000+62000

    def test_group_by_with_avg(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.AVG, column="age")
        result = engine.apply_aggregations(sample_df, [agg], group_by=["department"])
        eng_row = result[result["department"] == "Engineering"]
        mkt_row = result[result["department"] == "Marketing"]
        assert abs(eng_row["avg_age"].iloc[0] - (30 + 35 + 32) / 3) < 1e-10
        assert abs(mkt_row["avg_age"].iloc[0] - (25 + 28) / 2) < 1e-10

    def test_group_by_columns_first_in_output(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.SUM, column="salary")
        result = engine.apply_aggregations(sample_df, [agg], group_by=["department"])
        # group_by columns should come first
        assert result.columns[0] == "department"
        assert result.columns[1] == "sum_salary"

    def test_group_by_multiple_aggregations(self, engine, sample_df):
        aggs = [
            AggregationOp(function=AggregationFunction.COUNT, column="name"),
            AggregationOp(function=AggregationFunction.AVG, column="salary"),
        ]
        result = engine.apply_aggregations(sample_df, aggs, group_by=["department"])
        assert result.columns.tolist() == ["department", "count_name", "avg_salary"]
        assert len(result) == 2

    def test_group_by_resets_index(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.COUNT, column="name")
        result = engine.apply_aggregations(sample_df, [agg], group_by=["department"])
        # Index should be reset (0, 1, ...)
        assert list(result.index) == list(range(len(result)))


class TestApplyAggregationsEdgeCases:
    """Test edge cases."""

    def test_count_on_numeric_column(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.COUNT, column="age")
        result = engine.apply_aggregations(sample_df, [agg])
        assert result["count_age"].iloc[0] == 5

    def test_min_on_string_column(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.MIN, column="name")
        result = engine.apply_aggregations(sample_df, [agg])
        assert result["min_name"].iloc[0] == "Alice"

    def test_max_on_string_column(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.MAX, column="name")
        result = engine.apply_aggregations(sample_df, [agg])
        assert result["max_name"].iloc[0] == "Eve"

    def test_distinct_count_on_numeric_column(self, engine, sample_df):
        agg = AggregationOp(function=AggregationFunction.DISTINCT_COUNT, column="age")
        result = engine.apply_aggregations(sample_df, [agg])
        assert result["distinct_count_age"].iloc[0] == 5

    def test_aggregation_with_nulls(self, engine):
        df = pd.DataFrame(
            {
                "value": [1.0, 2.0, np.nan, 4.0, 5.0],
                "category": ["A", "A", "B", "B", "B"],
            }
        )
        agg = AggregationOp(function=AggregationFunction.SUM, column="value")
        result = engine.apply_aggregations(df, [agg])
        assert result["sum_value"].iloc[0] == 12.0  # NaN excluded by pandas

    def test_single_row_dataframe(self, engine):
        df = pd.DataFrame({"x": [42], "y": ["hello"]})
        agg = AggregationOp(function=AggregationFunction.SUM, column="x")
        result = engine.apply_aggregations(df, [agg])
        assert result["sum_x"].iloc[0] == 42
