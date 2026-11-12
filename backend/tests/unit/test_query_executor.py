"""Unit tests for the QueryExecutor service."""

import pandas as pd
import pytest

from app.exceptions import QueryExecutionError, QueryValidationError
from app.models.chat_schemas import QueryResult
from app.services.query_executor import QueryExecutor


@pytest.fixture
def executor():
    """Create a QueryExecutor instance."""
    return QueryExecutor()


@pytest.fixture
def sample_df():
    """Create a sample DataFrame for testing."""
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
            "age": [30, 25, 35, 28, 32],
            "created_at": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
            "update_count": [1, 2, 3, 4, 5],
        }
    )


class TestValidateQuery:
    """Tests for validate_query method."""

    def test_valid_select_query(self, executor):
        """Valid SELECT queries should pass validation."""
        executor.validate_query("SELECT * FROM dataset")

    def test_valid_select_with_where(self, executor):
        """SELECT with WHERE clause should pass."""
        executor.validate_query("SELECT name, age FROM dataset WHERE age > 30")

    def test_valid_select_with_aggregation(self, executor):
        """SELECT with aggregation functions should pass."""
        executor.validate_query("SELECT AVG(age), COUNT(*) FROM dataset GROUP BY name")

    def test_rejects_insert(self, executor):
        """INSERT statements should be rejected."""
        with pytest.raises(QueryValidationError):
            executor.validate_query("INSERT INTO dataset VALUES (1, 'test')")

    def test_rejects_update(self, executor):
        """UPDATE statements should be rejected."""
        with pytest.raises(QueryValidationError):
            executor.validate_query("UPDATE dataset SET name = 'test' WHERE id = 1")

    def test_rejects_delete(self, executor):
        """DELETE statements should be rejected."""
        with pytest.raises(QueryValidationError):
            executor.validate_query("DELETE FROM dataset WHERE id = 1")

    def test_rejects_drop(self, executor):
        """DROP statements should be rejected."""
        with pytest.raises(QueryValidationError):
            executor.validate_query("DROP TABLE dataset")

    def test_rejects_alter(self, executor):
        """ALTER statements should be rejected."""
        with pytest.raises(QueryValidationError):
            executor.validate_query("ALTER TABLE dataset ADD COLUMN new_col INTEGER")

    def test_rejects_create(self, executor):
        """CREATE statements should be rejected."""
        with pytest.raises(QueryValidationError):
            executor.validate_query("CREATE TABLE new_table (id INT)")

    def test_case_insensitive_rejection(self, executor):
        """Prohibited keywords should be detected case-insensitively."""
        with pytest.raises(QueryValidationError):
            executor.validate_query("insert INTO dataset VALUES (1, 'test')")
        with pytest.raises(QueryValidationError):
            executor.validate_query("Drop TABLE dataset")

    def test_no_false_positive_created_at(self, executor):
        """Column name 'created_at' should NOT trigger CREATE rejection."""
        executor.validate_query("SELECT created_at FROM dataset")

    def test_no_false_positive_update_count(self, executor):
        """Column name 'update_count' should NOT trigger UPDATE rejection."""
        executor.validate_query("SELECT update_count FROM dataset WHERE update_count > 3")

    def test_no_false_positive_dropoff_location(self, executor):
        """Column name 'dropoff_location' should NOT trigger DROP rejection."""
        executor.validate_query("SELECT dropoff_location FROM dataset")

    def test_no_false_positive_inserted_at(self, executor):
        """Column name 'inserted_at' should NOT trigger INSERT rejection."""
        executor.validate_query("SELECT inserted_at FROM dataset")

    def test_no_false_positive_deleted_flag(self, executor):
        """Column name 'deleted_flag' should NOT trigger DELETE rejection."""
        executor.validate_query("SELECT deleted_flag FROM dataset")

    def test_no_false_positive_altered_status(self, executor):
        """Column name 'altered_status' should NOT trigger ALTER rejection."""
        executor.validate_query("SELECT altered_status FROM dataset")

    def test_empty_query_rejected(self, executor):
        """Empty or whitespace-only queries should be rejected."""
        with pytest.raises(QueryValidationError):
            executor.validate_query("")
        with pytest.raises(QueryValidationError):
            executor.validate_query("   ")

    def test_error_message(self, executor):
        """Rejected queries should have the correct error message."""
        with pytest.raises(QueryValidationError) as exc_info:
            executor.validate_query("DROP TABLE dataset")
        assert "Operation not permitted" in str(exc_info.value)
        assert "SELECT" in str(exc_info.value)


class TestExecute:
    """Tests for execute method."""

    def test_simple_select_all(self, executor, sample_df):
        """Simple SELECT * should return all rows and columns."""
        result = executor.execute(sample_df, "SELECT * FROM dataset")
        assert isinstance(result, QueryResult)
        assert len(result.columns) == 5
        assert len(result.rows) == 5

    def test_select_specific_columns(self, executor, sample_df):
        """Selecting specific columns should work."""
        result = executor.execute(sample_df, "SELECT name, age FROM dataset")
        assert result.columns == ["name", "age"]
        assert len(result.rows) == 5

    def test_select_with_where(self, executor, sample_df):
        """WHERE clause should filter rows correctly."""
        result = executor.execute(sample_df, "SELECT * FROM dataset WHERE age > 30")
        assert len(result.rows) == 2  # Charlie (35) and Eve (32)

    def test_select_with_aggregation(self, executor, sample_df):
        """Aggregation queries should work."""
        result = executor.execute(sample_df, "SELECT COUNT(*) as cnt FROM dataset")
        assert len(result.rows) == 1
        assert result.rows[0]["cnt"] == 5

    def test_result_limit_10000(self, executor):
        """Results should be capped at 10,000 rows."""
        # Create a DataFrame with more than 10,000 rows
        large_df = pd.DataFrame({"value": range(15000)})
        result = executor.execute(large_df, "SELECT * FROM dataset")
        assert len(result.rows) == 10000

    def test_query_with_column_named_created_at(self, executor, sample_df):
        """Queries referencing 'created_at' column should work without false positive."""
        result = executor.execute(sample_df, "SELECT created_at FROM dataset")
        assert result.columns == ["created_at"]
        assert len(result.rows) == 5

    def test_query_with_column_named_update_count(self, executor, sample_df):
        """Queries referencing 'update_count' column should work without false positive."""
        result = executor.execute(sample_df, "SELECT update_count FROM dataset WHERE update_count > 3")
        assert len(result.rows) == 2

    def test_invalid_sql_raises_execution_error(self, executor, sample_df):
        """Invalid SQL should raise QueryExecutionError."""
        with pytest.raises(QueryExecutionError):
            executor.execute(sample_df, "SELECT nonexistent_column FROM dataset")

    def test_prohibited_keyword_raises_validation_error(self, executor, sample_df):
        """Prohibited keywords should raise QueryValidationError before execution."""
        with pytest.raises(QueryValidationError):
            executor.execute(sample_df, "DROP TABLE dataset")

    def test_result_structure(self, executor, sample_df):
        """Result should be a QueryResult with columns and rows."""
        result = executor.execute(sample_df, "SELECT name, age FROM dataset LIMIT 2")
        assert isinstance(result, QueryResult)
        assert isinstance(result.columns, list)
        assert isinstance(result.rows, list)
        assert all(isinstance(row, dict) for row in result.rows)
        assert all("name" in row and "age" in row for row in result.rows)

    def test_order_by_works(self, executor, sample_df):
        """ORDER BY should work properly."""
        result = executor.execute(sample_df, "SELECT name, age FROM dataset ORDER BY age DESC LIMIT 1")
        assert result.rows[0]["name"] == "Charlie"
        assert result.rows[0]["age"] == 35
