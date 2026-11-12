"""Unit tests for AnalyticsEngine.apply_pagination method."""

import pandas as pd
import pytest

from app.exceptions import AnalyticsValidationError
from app.models.analytics_schemas import PaginationMeta
from app.services.analytics_engine import AnalyticsEngine


@pytest.fixture
def engine():
    """Create an AnalyticsEngine instance."""
    return AnalyticsEngine()


@pytest.fixture
def sample_df():
    """Create a sample DataFrame with 10 rows for pagination testing."""
    return pd.DataFrame(
        {
            "id": list(range(1, 11)),
            "name": [f"item_{i}" for i in range(1, 11)],
            "value": [i * 10.0 for i in range(1, 11)],
        }
    )


@pytest.fixture
def empty_df():
    """Create an empty DataFrame with columns."""
    return pd.DataFrame({"id": [], "name": [], "value": []})


class TestApplyPaginationValidation:
    """Tests for input validation in apply_pagination."""

    def test_page_less_than_one_raises_error(self, engine, sample_df):
        """Page < 1 should raise AnalyticsValidationError."""
        with pytest.raises(AnalyticsValidationError, match="page must be a positive integer"):
            engine.apply_pagination(sample_df, page=0, page_size=5)

    def test_negative_page_raises_error(self, engine, sample_df):
        """Negative page should raise AnalyticsValidationError."""
        with pytest.raises(AnalyticsValidationError, match="page must be a positive integer"):
            engine.apply_pagination(sample_df, page=-1, page_size=5)

    def test_page_size_zero_raises_error(self, engine, sample_df):
        """page_size = 0 should raise AnalyticsValidationError."""
        with pytest.raises(AnalyticsValidationError, match="page_size must be between 1 and 1000"):
            engine.apply_pagination(sample_df, page=1, page_size=0)

    def test_page_size_negative_raises_error(self, engine, sample_df):
        """Negative page_size should raise AnalyticsValidationError."""
        with pytest.raises(AnalyticsValidationError, match="page_size must be between 1 and 1000"):
            engine.apply_pagination(sample_df, page=1, page_size=-1)

    def test_page_size_exceeds_1000_raises_error(self, engine, sample_df):
        """page_size > 1000 should raise AnalyticsValidationError."""
        with pytest.raises(AnalyticsValidationError, match="page_size must be between 1 and 1000"):
            engine.apply_pagination(sample_df, page=1, page_size=1001)


class TestApplyPaginationBasic:
    """Tests for basic pagination functionality."""

    def test_first_page(self, engine, sample_df):
        """First page should return the first page_size rows."""
        result_df, meta = engine.apply_pagination(sample_df, page=1, page_size=3)

        assert len(result_df) == 3
        assert list(result_df["id"]) == [1, 2, 3]
        assert meta.total_rows == 10
        assert meta.total_pages == 4  # ceil(10/3) = 4
        assert meta.current_page == 1
        assert meta.page_size == 3

    def test_middle_page(self, engine, sample_df):
        """Middle page should return the correct slice of rows."""
        result_df, meta = engine.apply_pagination(sample_df, page=2, page_size=3)

        assert len(result_df) == 3
        assert list(result_df["id"]) == [4, 5, 6]
        assert meta.current_page == 2

    def test_last_page_partial(self, engine, sample_df):
        """Last page may have fewer rows than page_size."""
        result_df, meta = engine.apply_pagination(sample_df, page=4, page_size=3)

        assert len(result_df) == 1
        assert list(result_df["id"]) == [10]
        assert meta.total_pages == 4

    def test_page_exceeds_total_pages_returns_empty(self, engine, sample_df):
        """Page beyond total_pages should return empty DataFrame with correct metadata."""
        result_df, meta = engine.apply_pagination(sample_df, page=5, page_size=3)

        assert len(result_df) == 0
        assert list(result_df.columns) == ["id", "name", "value"]
        assert meta.total_rows == 10
        assert meta.total_pages == 4
        assert meta.current_page == 5
        assert meta.page_size == 3

    def test_page_size_equals_total_rows(self, engine, sample_df):
        """When page_size equals total rows, single page with all data."""
        result_df, meta = engine.apply_pagination(sample_df, page=1, page_size=10)

        assert len(result_df) == 10
        assert meta.total_pages == 1

    def test_page_size_larger_than_total_rows(self, engine, sample_df):
        """When page_size > total rows, single page with all data."""
        result_df, meta = engine.apply_pagination(sample_df, page=1, page_size=100)

        assert len(result_df) == 10
        assert meta.total_pages == 1
        assert meta.total_rows == 10


class TestApplyPaginationEdgeCases:
    """Tests for edge cases in pagination."""

    def test_empty_dataframe(self, engine, empty_df):
        """Empty DataFrame should return 0 total_pages."""
        result_df, meta = engine.apply_pagination(empty_df, page=1, page_size=10)

        assert len(result_df) == 0
        assert meta.total_rows == 0
        assert meta.total_pages == 0
        assert meta.current_page == 1
        assert meta.page_size == 10

    def test_page_size_one(self, engine, sample_df):
        """page_size=1 should return one row per page."""
        result_df, meta = engine.apply_pagination(sample_df, page=1, page_size=1)

        assert len(result_df) == 1
        assert list(result_df["id"]) == [1]
        assert meta.total_pages == 10

    def test_page_size_1000_valid(self, engine, sample_df):
        """page_size=1000 is the maximum valid value."""
        result_df, meta = engine.apply_pagination(sample_df, page=1, page_size=1000)

        assert len(result_df) == 10
        assert meta.total_pages == 1
        assert meta.page_size == 1000

    def test_reset_index(self, engine, sample_df):
        """Result should have a reset index starting from 0."""
        result_df, _ = engine.apply_pagination(sample_df, page=2, page_size=3)

        assert list(result_df.index) == [0, 1, 2]

    def test_single_row_dataframe(self, engine):
        """Single row DataFrame paginated correctly."""
        df = pd.DataFrame({"x": [42]})
        result_df, meta = engine.apply_pagination(df, page=1, page_size=10)

        assert len(result_df) == 1
        assert meta.total_rows == 1
        assert meta.total_pages == 1

    def test_columns_preserved_on_empty_page(self, engine, sample_df):
        """When page exceeds total, columns are still preserved."""
        result_df, _ = engine.apply_pagination(sample_df, page=100, page_size=5)

        assert list(result_df.columns) == ["id", "name", "value"]
        assert len(result_df) == 0
