"""Unit tests for AnalyticsEngine.apply_search method."""

import pandas as pd
import pytest

from app.exceptions import AnalyticsValidationError
from app.services.analytics_engine import AnalyticsEngine


@pytest.fixture
def engine():
    return AnalyticsEngine()


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        {
            "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
            "city": ["New York", "Boston", "Chicago", "New Orleans", "Denver"],
            "age": [30, 25, 35, 28, 22],
        }
    )


class TestApplySearchNoneOrEmpty:
    """Tests for when search is None or empty string."""

    def test_returns_unchanged_when_search_is_none(self, engine, sample_df):
        result = engine.apply_search(sample_df, None)
        pd.testing.assert_frame_equal(result, sample_df)

    def test_returns_unchanged_when_search_is_empty_string(self, engine, sample_df):
        result = engine.apply_search(sample_df, "")
        pd.testing.assert_frame_equal(result, sample_df)

    def test_returns_unchanged_when_search_is_none_with_search_columns(
        self, engine, sample_df
    ):
        result = engine.apply_search(sample_df, None, search_columns=["name"])
        pd.testing.assert_frame_equal(result, sample_df)


class TestApplySearchAllColumns:
    """Tests for search across all columns (no search_columns specified)."""

    def test_finds_match_in_string_column(self, engine, sample_df):
        result = engine.apply_search(sample_df, "alice")
        assert len(result) == 1
        assert result.iloc[0]["name"] == "Alice"

    def test_case_insensitive_match(self, engine, sample_df):
        result = engine.apply_search(sample_df, "ALICE")
        assert len(result) == 1
        assert result.iloc[0]["name"] == "Alice"

    def test_substring_match(self, engine, sample_df):
        result = engine.apply_search(sample_df, "new")
        # "New York" and "New Orleans" match
        assert len(result) == 2
        assert set(result["city"]) == {"New York", "New Orleans"}

    def test_matches_numeric_column_as_string(self, engine, sample_df):
        result = engine.apply_search(sample_df, "30")
        assert len(result) == 1
        assert result.iloc[0]["name"] == "Alice"

    def test_no_match_returns_empty_dataframe(self, engine, sample_df):
        result = engine.apply_search(sample_df, "zzz_no_match")
        assert len(result) == 0
        assert list(result.columns) == ["name", "city", "age"]

    def test_matches_across_multiple_columns(self, engine):
        df = pd.DataFrame(
            {
                "first": ["John", "Jane"],
                "last": ["Smith", "Johnson"],
            }
        )
        result = engine.apply_search(df, "john")
        # "John" in first col, "Johnson" in last col
        assert len(result) == 2


class TestApplySearchWithSearchColumns:
    """Tests for search restricted to specific columns."""

    def test_restricts_search_to_specified_columns(self, engine, sample_df):
        # "30" appears in age column but not in name
        result = engine.apply_search(sample_df, "30", search_columns=["name"])
        assert len(result) == 0

    def test_finds_match_in_specified_column(self, engine, sample_df):
        result = engine.apply_search(sample_df, "alice", search_columns=["name"])
        assert len(result) == 1
        assert result.iloc[0]["name"] == "Alice"

    def test_searches_multiple_specified_columns(self, engine, sample_df):
        result = engine.apply_search(
            sample_df, "new", search_columns=["name", "city"]
        )
        # "New York" and "New Orleans" in city column
        assert len(result) == 2


class TestApplySearchValidation:
    """Tests for search_columns validation."""

    def test_raises_error_for_invalid_column(self, engine, sample_df):
        with pytest.raises(AnalyticsValidationError) as exc_info:
            engine.apply_search(sample_df, "test", search_columns=["nonexistent"])
        assert "nonexistent" in str(exc_info.value)
        assert "does not exist" in str(exc_info.value)

    def test_raises_error_for_one_invalid_in_list(self, engine, sample_df):
        with pytest.raises(AnalyticsValidationError) as exc_info:
            engine.apply_search(
                sample_df, "test", search_columns=["name", "invalid_col"]
            )
        assert "invalid_col" in str(exc_info.value)

    def test_does_not_validate_columns_when_search_is_none(self, engine, sample_df):
        # No error raised since search is None — columns not validated
        result = engine.apply_search(sample_df, None, search_columns=["nonexistent"])
        pd.testing.assert_frame_equal(result, sample_df)

    def test_does_not_validate_columns_when_search_is_empty(self, engine, sample_df):
        # No error raised since search is empty
        result = engine.apply_search(sample_df, "", search_columns=["nonexistent"])
        pd.testing.assert_frame_equal(result, sample_df)


class TestApplySearchIndexReset:
    """Tests that the index is reset in the result."""

    def test_result_has_reset_index(self, engine, sample_df):
        result = engine.apply_search(sample_df, "diana")
        assert list(result.index) == [0]

    def test_multiple_results_have_contiguous_index(self, engine, sample_df):
        result = engine.apply_search(sample_df, "new")
        assert list(result.index) == [0, 1]


class TestApplySearchEdgeCases:
    """Tests for edge cases."""

    def test_empty_dataframe(self, engine):
        df = pd.DataFrame({"col": pd.Series([], dtype=str)})
        result = engine.apply_search(df, "test")
        assert len(result) == 0

    def test_null_values_in_column(self, engine):
        df = pd.DataFrame({"name": ["Alice", None, "Bob"]})
        result = engine.apply_search(df, "alice")
        assert len(result) == 1
        assert result.iloc[0]["name"] == "Alice"

    def test_null_values_converted_to_nan_string(self, engine):
        df = pd.DataFrame({"name": ["Alice", None, "Bob"]})
        # None/NaN values don't match any search term
        result = engine.apply_search(df, "nan")
        # With na=False, NaN entries are excluded from matches
        assert len(result) == 0
