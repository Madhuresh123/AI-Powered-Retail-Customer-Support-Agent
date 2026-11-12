"""Unit tests for SQLEngine service."""

import pandas as pd
import pytest

from app.exceptions import AnalyticsValidationError
from app.services.sql_engine import SQLEngine


@pytest.fixture
def engine():
    """Create an SQLEngine instance."""
    return SQLEngine()


@pytest.fixture
def sample_df():
    """Create a sample DataFrame for testing."""
    return pd.DataFrame(
        {
            "name": ["Alice", "Bob", "Charlie", "Diana"],
            "age": [30, 25, 35, 28],
            "city": ["New York", "London", "Paris", "Tokyo"],
            "salary": [70000.0, 55000.0, 80000.0, 65000.0],
        }
    )


class TestValidateQuery:
    """Tests for validate_query method."""

    def test_valid_select_query(self, engine):
        """A simple SELECT query should pass validation."""
        engine.validate_query("SELECT * FROM dataset")

    def test_valid_select_with_where(self, engine):
        """A SELECT with WHERE clause should pass validation."""
        engine.validate_query("SELECT name, age FROM dataset WHERE age > 25")

    def test_valid_select_with_order_by(self, engine):
        """A SELECT with ORDER BY should pass validation."""
        engine.validate_query("SELECT * FROM dataset ORDER BY age DESC")

    def test_valid_select_with_group_by(self, engine):
        """A SELECT with GROUP BY should pass validation."""
        engine.validate_query("SELECT city, COUNT(*) FROM dataset GROUP BY city")

    def test_empty_query_raises(self, engine):
        """An empty query should raise AnalyticsValidationError."""
        with pytest.raises(AnalyticsValidationError, match="1 and 4096 characters"):
            engine.validate_query("")

    def test_whitespace_only_query_raises(self, engine):
        """A whitespace-only query should raise AnalyticsValidationError."""
        with pytest.raises(AnalyticsValidationError, match="1 and 4096 characters"):
            engine.validate_query("   ")

    def test_too_long_query_raises(self, engine):
        """A query longer than 4096 characters should raise."""
        long_query = "SELECT * FROM dataset WHERE " + "a" * 4100
        with pytest.raises(AnalyticsValidationError, match="1 and 4096 characters"):
            engine.validate_query(long_query)

    def test_multiple_statements_raises(self, engine):
        """Multiple statements separated by semicolons should raise."""
        with pytest.raises(AnalyticsValidationError, match="single SELECT"):
            engine.validate_query("SELECT * FROM dataset; DROP TABLE dataset")

    def test_non_select_statement_raises(self, engine):
        """A non-SELECT statement should raise."""
        with pytest.raises(AnalyticsValidationError, match="single SELECT"):
            engine.validate_query("INSERT INTO dataset VALUES (1, 2)")

    def test_insert_keyword_in_select_raises(self, engine):
        """INSERT keyword anywhere in query should raise."""
        with pytest.raises(AnalyticsValidationError, match="single SELECT"):
            engine.validate_query("SELECT * FROM dataset; INSERT INTO x VALUES (1)")

    def test_update_keyword_raises(self, engine):
        """UPDATE keyword should raise."""
        with pytest.raises(AnalyticsValidationError, match="single SELECT"):
            engine.validate_query("UPDATE dataset SET age = 10")

    def test_delete_keyword_raises(self, engine):
        """DELETE keyword should raise."""
        with pytest.raises(AnalyticsValidationError, match="single SELECT"):
            engine.validate_query("DELETE FROM dataset")

    def test_drop_keyword_raises(self, engine):
        """DROP keyword in a SELECT context should raise."""
        with pytest.raises(AnalyticsValidationError, match="single SELECT"):
            engine.validate_query("SELECT * FROM dataset; DROP TABLE dataset")

    def test_subquery_raises(self, engine):
        """Subqueries (nested SELECT) should raise."""
        with pytest.raises(AnalyticsValidationError, match="subqueries"):
            engine.validate_query(
                "SELECT * FROM dataset WHERE age IN (SELECT age FROM dataset)"
            )

    def test_join_raises(self, engine):
        """JOIN keyword should raise."""
        with pytest.raises(AnalyticsValidationError, match="JOIN"):
            engine.validate_query(
                "SELECT * FROM dataset JOIN other ON dataset.id = other.id"
            )

    def test_union_raises(self, engine):
        """UNION keyword should raise."""
        with pytest.raises(AnalyticsValidationError, match="UNION"):
            engine.validate_query(
                "SELECT name FROM dataset UNION SELECT name FROM dataset"
            )

    def test_window_function_raises(self, engine):
        """Window functions (OVER clause) should raise."""
        with pytest.raises(AnalyticsValidationError, match="window functions"):
            engine.validate_query(
                "SELECT name, ROW_NUMBER() OVER (ORDER BY age) FROM dataset"
            )

    def test_window_function_no_space_raises(self, engine):
        """Window functions with OVER( (no space) should raise."""
        with pytest.raises(AnalyticsValidationError, match="window functions"):
            engine.validate_query(
                "SELECT name, RANK() OVER(PARTITION BY city) FROM dataset"
            )


class TestExecute:
    """Tests for execute method."""

    def test_select_all(self, engine, sample_df):
        """SELECT * should return all columns and rows."""
        result = engine.execute(sample_df, "SELECT * FROM dataset")
        assert result.columns == ["name", "age", "city", "salary"]
        assert len(result.rows) == 4

    def test_select_specific_columns(self, engine, sample_df):
        """SELECT specific columns should return only those columns."""
        result = engine.execute(sample_df, "SELECT name, age FROM dataset")
        assert result.columns == ["name", "age"]
        assert len(result.rows) == 4
        assert result.rows[0]["name"] == "Alice"

    def test_where_clause(self, engine, sample_df):
        """WHERE clause should filter rows."""
        result = engine.execute(sample_df, "SELECT * FROM dataset WHERE age > 28")
        assert len(result.rows) == 2
        ages = [row["age"] for row in result.rows]
        assert all(age > 28 for age in ages)

    def test_order_by(self, engine, sample_df):
        """ORDER BY should sort results."""
        result = engine.execute(
            sample_df, "SELECT name, age FROM dataset ORDER BY age ASC"
        )
        ages = [row["age"] for row in result.rows]
        assert ages == sorted(ages)

    def test_group_by_with_aggregate(self, engine, sample_df):
        """GROUP BY with aggregate function should work."""
        result = engine.execute(
            sample_df, "SELECT city, COUNT(*) as cnt FROM dataset GROUP BY city"
        )
        assert "city" in result.columns
        assert "cnt" in result.columns

    def test_limit_clause(self, engine, sample_df):
        """LIMIT clause should restrict row count."""
        result = engine.execute(sample_df, "SELECT * FROM dataset LIMIT 2")
        assert len(result.rows) == 2

    def test_result_limited_to_10000_rows(self, engine):
        """Results should be capped at 10,000 rows."""
        large_df = pd.DataFrame({"x": range(15000)})
        result = engine.execute(large_df, "SELECT * FROM dataset")
        assert len(result.rows) == 10000

    def test_null_values_as_none(self, engine):
        """NULL values should appear as None in results."""
        df = pd.DataFrame({"a": [1, None, 3], "b": ["x", "y", None]})
        result = engine.execute(df, "SELECT * FROM dataset")
        # At least one None should be present
        has_none = any(
            v is None for row in result.rows for v in row.values()
        )
        assert has_none

    def test_unknown_column_raises(self, engine, sample_df):
        """Referencing a non-existent column should raise."""
        with pytest.raises(AnalyticsValidationError):
            engine.execute(sample_df, "SELECT nonexistent FROM dataset")

    def test_syntax_error_raises(self, engine, sample_df):
        """A query with syntax errors should raise."""
        with pytest.raises(AnalyticsValidationError):
            engine.execute(sample_df, "SELEC * FORM dataset")

    def test_having_clause(self, engine, sample_df):
        """HAVING clause should work with GROUP BY."""
        result = engine.execute(
            sample_df,
            "SELECT city, COUNT(*) as cnt FROM dataset GROUP BY city HAVING cnt >= 1",
        )
        assert len(result.rows) >= 1

    def test_returns_sql_response_type(self, engine, sample_df):
        """The execute method should return an SQLResponse object."""
        from app.models.analytics_schemas import SQLResponse

        result = engine.execute(sample_df, "SELECT * FROM dataset")
        assert isinstance(result, SQLResponse)
