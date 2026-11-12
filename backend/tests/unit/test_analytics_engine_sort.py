"""Unit tests for AnalyticsEngine.apply_sort method."""

import numpy as np
import pandas as pd
import pytest

from app.exceptions import AnalyticsValidationError
from app.models.analytics_schemas import SortDirection, SortSpec
from app.services.analytics_engine import AnalyticsEngine


@pytest.fixture
def engine():
    """Create an AnalyticsEngine instance."""
    return AnalyticsEngine()


@pytest.fixture
def sample_df():
    """Create a sample DataFrame for testing."""
    return pd.DataFrame(
        {
            "name": ["Charlie", "alice", "Bob", "David", "Eve"],
            "age": [30, 25, 35, 28, 32],
            "score": [85.5, 92.0, 78.3, 88.1, 91.5],
        }
    )


@pytest.fixture
def df_with_nulls():
    """Create a DataFrame with null values for null-last testing."""
    return pd.DataFrame(
        {
            "name": ["Alice", None, "Charlie", "Bob", None],
            "age": [30, 25, None, 28, None],
            "score": [85.5, None, 78.3, None, 91.5],
        }
    )


class TestApplySortBasic:
    """Test basic sort functionality."""

    def test_none_sort_returns_unchanged(self, engine, sample_df):
        """Return df unchanged when sort is None."""
        result = engine.apply_sort(sample_df, None)
        pd.testing.assert_frame_equal(result, sample_df)

    def test_empty_sort_returns_unchanged(self, engine, sample_df):
        """Return df unchanged when sort is empty list."""
        result = engine.apply_sort(sample_df, [])
        pd.testing.assert_frame_equal(result, sample_df)

    def test_sort_numeric_ascending(self, engine, sample_df):
        """Sort numeric column ascending."""
        sort = [SortSpec(column="age", direction=SortDirection.ASC)]
        result = engine.apply_sort(sample_df, sort)
        assert list(result["age"]) == [25, 28, 30, 32, 35]

    def test_sort_numeric_descending(self, engine, sample_df):
        """Sort numeric column descending."""
        sort = [SortSpec(column="age", direction=SortDirection.DESC)]
        result = engine.apply_sort(sample_df, sort)
        assert list(result["age"]) == [35, 32, 30, 28, 25]

    def test_sort_preserves_all_columns(self, engine, sample_df):
        """Sort preserves all columns in the DataFrame."""
        sort = [SortSpec(column="age", direction=SortDirection.ASC)]
        result = engine.apply_sort(sample_df, sort)
        assert list(result.columns) == ["name", "age", "score"]
        assert len(result) == len(sample_df)

    def test_sort_resets_index(self, engine, sample_df):
        """Sort resets the index to sequential integers."""
        sort = [SortSpec(column="age", direction=SortDirection.DESC)]
        result = engine.apply_sort(sample_df, sort)
        assert list(result.index) == [0, 1, 2, 3, 4]


class TestApplySortCaseInsensitive:
    """Test case-insensitive string sorting."""

    def test_sort_string_case_insensitive_asc(self, engine, sample_df):
        """String sort is case-insensitive ascending."""
        sort = [SortSpec(column="name", direction=SortDirection.ASC)]
        result = engine.apply_sort(sample_df, sort)
        # Expected case-insensitive order: alice, Bob, Charlie, David, Eve
        assert list(result["name"]) == ["alice", "Bob", "Charlie", "David", "Eve"]

    def test_sort_string_case_insensitive_desc(self, engine, sample_df):
        """String sort is case-insensitive descending."""
        sort = [SortSpec(column="name", direction=SortDirection.DESC)]
        result = engine.apply_sort(sample_df, sort)
        # Expected case-insensitive order reversed: Eve, David, Charlie, Bob, alice
        assert list(result["name"]) == ["Eve", "David", "Charlie", "Bob", "alice"]

    def test_sort_preserves_original_case(self, engine, sample_df):
        """Sort preserves original string values (not lowercased)."""
        sort = [SortSpec(column="name", direction=SortDirection.ASC)]
        result = engine.apply_sort(sample_df, sort)
        # Original values are preserved
        assert "alice" in result["name"].values
        assert "Bob" in result["name"].values


class TestApplySortNullLast:
    """Test null-last behavior."""

    def test_nulls_last_ascending(self, engine, df_with_nulls):
        """Null values appear last when sorting ascending."""
        sort = [SortSpec(column="age", direction=SortDirection.ASC)]
        result = engine.apply_sort(df_with_nulls, sort)
        ages = list(result["age"])
        # Non-null values should be sorted first, nulls at end
        non_nulls = [a for a in ages if pd.notna(a)]
        assert non_nulls == sorted(non_nulls)
        # Last two should be null
        assert pd.isna(ages[-1])
        assert pd.isna(ages[-2])

    def test_nulls_last_descending(self, engine, df_with_nulls):
        """Null values appear last when sorting descending."""
        sort = [SortSpec(column="age", direction=SortDirection.DESC)]
        result = engine.apply_sort(df_with_nulls, sort)
        ages = list(result["age"])
        # Non-null values should be sorted descending first, nulls at end
        non_nulls = [a for a in ages if pd.notna(a)]
        assert non_nulls == sorted(non_nulls, reverse=True)
        # Last two should be null
        assert pd.isna(ages[-1])
        assert pd.isna(ages[-2])

    def test_nulls_last_string_ascending(self, engine, df_with_nulls):
        """Null string values appear last when sorting ascending."""
        sort = [SortSpec(column="name", direction=SortDirection.ASC)]
        result = engine.apply_sort(df_with_nulls, sort)
        names = list(result["name"])
        # Last two should be null
        assert pd.isna(names[-1])
        assert pd.isna(names[-2])


class TestApplySortMultiColumn:
    """Test multi-column sorting."""

    def test_multi_column_sort(self, engine):
        """Multi-column sort uses priority order."""
        df = pd.DataFrame(
            {
                "dept": ["Sales", "Engineering", "Sales", "Engineering"],
                "name": ["Bob", "Alice", "Alice", "Bob"],
                "salary": [50000, 60000, 55000, 65000],
            }
        )
        sort = [
            SortSpec(column="dept", direction=SortDirection.ASC),
            SortSpec(column="name", direction=SortDirection.ASC),
        ]
        result = engine.apply_sort(df, sort)
        # Primary: dept asc, Secondary: name asc
        assert list(result["dept"]) == [
            "Engineering",
            "Engineering",
            "Sales",
            "Sales",
        ]
        assert list(result["name"]) == ["Alice", "Bob", "Alice", "Bob"]

    def test_multi_column_mixed_directions(self, engine):
        """Multi-column sort with mixed asc/desc directions."""
        df = pd.DataFrame(
            {
                "category": ["A", "A", "B", "B"],
                "value": [10, 20, 10, 20],
            }
        )
        sort = [
            SortSpec(column="category", direction=SortDirection.ASC),
            SortSpec(column="value", direction=SortDirection.DESC),
        ]
        result = engine.apply_sort(df, sort)
        assert list(result["category"]) == ["A", "A", "B", "B"]
        assert list(result["value"]) == [20, 10, 20, 10]


class TestApplySortValidation:
    """Test validation and error handling."""

    def test_invalid_column_raises_error(self, engine, sample_df):
        """Raise AnalyticsValidationError for non-existent column."""
        sort = [SortSpec(column="nonexistent", direction=SortDirection.ASC)]
        with pytest.raises(AnalyticsValidationError) as exc_info:
            engine.apply_sort(sample_df, sort)
        assert "nonexistent" in str(exc_info.value)
        assert "does not exist" in str(exc_info.value)

    def test_more_than_10_sort_columns_raises_error(self, engine):
        """Raise AnalyticsValidationError when more than 10 sort columns."""
        df = pd.DataFrame({f"col{i}": [1, 2, 3] for i in range(11)})
        sort = [
            SortSpec(column=f"col{i}", direction=SortDirection.ASC)
            for i in range(11)
        ]
        with pytest.raises(AnalyticsValidationError) as exc_info:
            engine.apply_sort(df, sort)
        assert "Maximum of 10 sort columns allowed" in str(exc_info.value)

    def test_exactly_10_sort_columns_works(self, engine):
        """Exactly 10 sort columns should work without error."""
        df = pd.DataFrame({f"col{i}": [1, 2, 3] for i in range(10)})
        sort = [
            SortSpec(column=f"col{i}", direction=SortDirection.ASC)
            for i in range(10)
        ]
        result = engine.apply_sort(df, sort)
        assert len(result) == 3

    def test_empty_dataframe_sort(self, engine):
        """Sort on empty DataFrame returns empty DataFrame."""
        df = pd.DataFrame({"name": [], "age": []})
        sort = [SortSpec(column="name", direction=SortDirection.ASC)]
        result = engine.apply_sort(df, sort)
        assert len(result) == 0
        assert list(result.columns) == ["name", "age"]
