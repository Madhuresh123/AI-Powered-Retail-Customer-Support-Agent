"""Unit tests for AnalyticsEngine.apply_filters method."""

import numpy as np
import pandas as pd
import pytest

from app.exceptions import AnalyticsValidationError
from app.models.analytics_schemas import FilterExpression, FilterOperator
from app.services.analytics_engine import AnalyticsEngine


@pytest.fixture
def engine():
    return AnalyticsEngine()


@pytest.fixture
def sample_df():
    """DataFrame with mixed numeric and string columns including nulls."""
    return pd.DataFrame(
        {
            "age": [25, 30, 35, 40, None, 50],
            "name": ["Alice", "Bob", "Charlie", None, "Eve", "Frank"],
            "salary": [50000, 60000, 70000, 80000, 90000, None],
            "city": ["New York", "Boston", "new york", "Chicago", "Boston", "Denver"],
        }
    )


class TestFilterIdentity:
    """Tests for returning unmodified DataFrame when no filters applied."""

    def test_none_filters_returns_unchanged(self, engine, sample_df):
        result = engine.apply_filters(sample_df, None)
        pd.testing.assert_frame_equal(result, sample_df)

    def test_empty_filters_returns_unchanged(self, engine, sample_df):
        result = engine.apply_filters(sample_df, [])
        pd.testing.assert_frame_equal(result, sample_df)


class TestNumericOperators:
    """Tests for numeric filter operators."""

    def test_eq_numeric(self, engine, sample_df):
        filt = FilterExpression(column="age", operator=FilterOperator.EQ, value=30)
        result = engine.apply_filters(sample_df, [filt])
        assert len(result) == 1
        assert result.iloc[0]["name"] == "Bob"

    def test_neq_numeric(self, engine, sample_df):
        filt = FilterExpression(column="age", operator=FilterOperator.NEQ, value=30)
        result = engine.apply_filters(sample_df, [filt])
        # Excludes Bob (age=30) and the null row
        assert 30 not in result["age"].values
        assert all(result["age"].notna())

    def test_gt_numeric(self, engine, sample_df):
        filt = FilterExpression(column="age", operator=FilterOperator.GT, value=35)
        result = engine.apply_filters(sample_df, [filt])
        assert all(result["age"] > 35)
        assert len(result) == 2  # age 40 and 50

    def test_gte_numeric(self, engine, sample_df):
        filt = FilterExpression(column="age", operator=FilterOperator.GTE, value=35)
        result = engine.apply_filters(sample_df, [filt])
        assert all(result["age"] >= 35)
        assert len(result) == 3  # age 35, 40, 50

    def test_lt_numeric(self, engine, sample_df):
        filt = FilterExpression(column="age", operator=FilterOperator.LT, value=35)
        result = engine.apply_filters(sample_df, [filt])
        assert all(result["age"] < 35)
        assert len(result) == 2  # age 25, 30

    def test_lte_numeric(self, engine, sample_df):
        filt = FilterExpression(column="age", operator=FilterOperator.LTE, value=35)
        result = engine.apply_filters(sample_df, [filt])
        assert all(result["age"] <= 35)
        assert len(result) == 3  # age 25, 30, 35

    def test_between_numeric(self, engine, sample_df):
        filt = FilterExpression(
            column="age", operator=FilterOperator.BETWEEN, value=[30, 40]
        )
        result = engine.apply_filters(sample_df, [filt])
        assert all((result["age"] >= 30) & (result["age"] <= 40))
        assert len(result) == 3  # age 30, 35, 40


class TestStringOperators:
    """Tests for string filter operators."""

    def test_eq_string(self, engine, sample_df):
        filt = FilterExpression(column="name", operator=FilterOperator.EQ, value="Alice")
        result = engine.apply_filters(sample_df, [filt])
        assert len(result) == 1
        assert result.iloc[0]["name"] == "Alice"

    def test_neq_string(self, engine, sample_df):
        filt = FilterExpression(column="name", operator=FilterOperator.NEQ, value="Alice")
        result = engine.apply_filters(sample_df, [filt])
        assert "Alice" not in result["name"].values
        assert all(result["name"].notna())

    def test_contains_case_insensitive(self, engine, sample_df):
        filt = FilterExpression(
            column="city", operator=FilterOperator.CONTAINS, value="new"
        )
        result = engine.apply_filters(sample_df, [filt])
        # Should match "New York" and "new york" (case-insensitive)
        assert len(result) == 2

    def test_starts_with_case_insensitive(self, engine, sample_df):
        filt = FilterExpression(
            column="city", operator=FilterOperator.STARTS_WITH, value="bos"
        )
        result = engine.apply_filters(sample_df, [filt])
        assert len(result) == 2  # Both "Boston" entries

    def test_ends_with_case_insensitive(self, engine, sample_df):
        filt = FilterExpression(
            column="city", operator=FilterOperator.ENDS_WITH, value="york"
        )
        result = engine.apply_filters(sample_df, [filt])
        assert len(result) == 2  # "New York" and "new york"

    def test_in_operator_case_sensitive(self, engine, sample_df):
        filt = FilterExpression(
            column="city", operator=FilterOperator.IN, value=["Boston", "Denver"]
        )
        result = engine.apply_filters(sample_df, [filt])
        assert len(result) == 3  # Two Bostons + Denver
        assert all(result["city"].isin(["Boston", "Denver"]))


class TestNullHandling:
    """Tests for null exclusion logic."""

    def test_null_excluded_in_numeric_filter(self, engine, sample_df):
        filt = FilterExpression(column="age", operator=FilterOperator.GT, value=0)
        result = engine.apply_filters(sample_df, [filt])
        # Null row (index 4) should be excluded
        assert all(result["age"].notna())

    def test_null_excluded_in_string_filter(self, engine, sample_df):
        filt = FilterExpression(
            column="name", operator=FilterOperator.CONTAINS, value="a"
        )
        result = engine.apply_filters(sample_df, [filt])
        assert all(result["name"].notna())

    def test_eq_null_returns_null_rows(self, engine, sample_df):
        filt = FilterExpression(column="name", operator=FilterOperator.EQ, value=None)
        result = engine.apply_filters(sample_df, [filt])
        assert len(result) == 1
        assert pd.isna(result.iloc[0]["name"])


class TestMultipleFilters:
    """Tests for logical AND combination of filters."""

    def test_multiple_filters_and_logic(self, engine, sample_df):
        filters = [
            FilterExpression(column="age", operator=FilterOperator.GTE, value=30),
            FilterExpression(column="age", operator=FilterOperator.LTE, value=40),
        ]
        result = engine.apply_filters(sample_df, filters)
        assert all((result["age"] >= 30) & (result["age"] <= 40))
        assert len(result) == 3  # 30, 35, 40

    def test_filters_on_different_columns(self, engine, sample_df):
        filters = [
            FilterExpression(column="age", operator=FilterOperator.GTE, value=30),
            FilterExpression(
                column="city", operator=FilterOperator.EQ, value="Boston"
            ),
        ]
        result = engine.apply_filters(sample_df, filters)
        assert all(result["age"] >= 30)
        assert all(result["city"] == "Boston")


class TestValidation:
    """Tests for validation and error raising."""

    def test_invalid_column_raises_error(self, engine, sample_df):
        filt = FilterExpression(
            column="nonexistent", operator=FilterOperator.EQ, value=1
        )
        with pytest.raises(AnalyticsValidationError, match="does not exist"):
            engine.apply_filters(sample_df, [filt])

    def test_numeric_op_on_string_column_raises_error(self, engine, sample_df):
        filt = FilterExpression(column="name", operator=FilterOperator.GT, value="A")
        with pytest.raises(AnalyticsValidationError, match="not numeric"):
            engine.apply_filters(sample_df, [filt])

    def test_string_op_on_numeric_column_raises_error(self, engine, sample_df):
        filt = FilterExpression(
            column="age", operator=FilterOperator.CONTAINS, value="2"
        )
        with pytest.raises(AnalyticsValidationError, match="numeric.*cannot apply"):
            engine.apply_filters(sample_df, [filt])

    def test_between_not_list_raises_error(self, engine, sample_df):
        filt = FilterExpression(column="age", operator=FilterOperator.BETWEEN, value=30)
        with pytest.raises(AnalyticsValidationError, match="between operator requires"):
            engine.apply_filters(sample_df, [filt])

    def test_between_wrong_length_raises_error(self, engine, sample_df):
        filt = FilterExpression(
            column="age", operator=FilterOperator.BETWEEN, value=[30]
        )
        with pytest.raises(AnalyticsValidationError, match="between operator requires"):
            engine.apply_filters(sample_df, [filt])

    def test_between_min_greater_than_max_raises_error(self, engine, sample_df):
        filt = FilterExpression(
            column="age", operator=FilterOperator.BETWEEN, value=[40, 30]
        )
        with pytest.raises(AnalyticsValidationError, match="between operator requires"):
            engine.apply_filters(sample_df, [filt])

    def test_in_operator_exceeds_100_items(self, engine, sample_df):
        filt = FilterExpression(
            column="city",
            operator=FilterOperator.IN,
            value=[f"city_{i}" for i in range(101)],
        )
        with pytest.raises(AnalyticsValidationError, match="up to 100 items"):
            engine.apply_filters(sample_df, [filt])
