"""Unit tests for the SQLGenerator service."""

from unittest.mock import MagicMock

import pytest

from app.exceptions import QueryValidationError
from app.models.chat_schemas import LLMResponse
from app.services.sql_generator import SQLGenerator


@pytest.fixture
def mock_llm_service():
    """Create a mock LLMService."""
    return MagicMock()


@pytest.fixture
def sql_generator(mock_llm_service):
    """Create an SQLGenerator with a mocked LLMService."""
    return SQLGenerator(llm_service=mock_llm_service)


class TestGenerateSQL:
    """Tests for SQLGenerator.generate_sql method."""

    def test_returns_sql_on_valid_select(self, sql_generator, mock_llm_service):
        """Should return the SQL string when LLM returns a valid SELECT query."""
        mock_llm_service.generate.return_value = LLMResponse(
            response_type="sql",
            sql="SELECT * FROM dataset",
            answer=None,
        )

        result = sql_generator.generate_sql("What are all the records?")

        assert result == "SELECT * FROM dataset"
        mock_llm_service.generate.assert_called_once_with(
            "What are all the records?"
        )

    def test_returns_sql_case_insensitive_select(self, sql_generator, mock_llm_service):
        """Should accept SQL that starts with 'select' in any case."""
        mock_llm_service.generate.return_value = LLMResponse(
            response_type="sql",
            sql="select region, avg(sales) from dataset group by region",
            answer=None,
        )

        result = sql_generator.generate_sql("Average sales by region")

        assert result == "select region, avg(sales) from dataset group by region"

    def test_strips_whitespace_from_sql(self, sql_generator, mock_llm_service):
        """Should strip leading/trailing whitespace from the SQL."""
        mock_llm_service.generate.return_value = LLMResponse(
            response_type="sql",
            sql="  SELECT COUNT(*) FROM dataset  ",
            answer=None,
        )

        result = sql_generator.generate_sql("How many records?")

        assert result == "SELECT COUNT(*) FROM dataset"

    def test_raises_error_when_response_type_is_answer(
        self, sql_generator, mock_llm_service
    ):
        """Should raise QueryValidationError when LLM returns an answer instead of SQL."""
        mock_llm_service.generate.return_value = LLMResponse(
            response_type="answer",
            sql=None,
            answer="I cannot generate SQL for this question.",
        )

        with pytest.raises(QueryValidationError) as exc_info:
            sql_generator.generate_sql("Tell me a joke")

        assert "Could not generate a valid query" in exc_info.value.message

    def test_raises_error_when_sql_is_none(self, sql_generator, mock_llm_service):
        """Should raise QueryValidationError when response_type is sql but sql field is None."""
        mock_llm_service.generate.return_value = LLMResponse(
            response_type="sql",
            sql=None,
            answer=None,
        )

        with pytest.raises(QueryValidationError):
            sql_generator.generate_sql("Some prompt")

    def test_raises_error_when_sql_is_empty_string(
        self, sql_generator, mock_llm_service
    ):
        """Should raise QueryValidationError when sql field is an empty string."""
        mock_llm_service.generate.return_value = LLMResponse(
            response_type="sql",
            sql="",
            answer=None,
        )

        with pytest.raises(QueryValidationError):
            sql_generator.generate_sql("Some prompt")

    def test_raises_error_when_sql_does_not_start_with_select(
        self, sql_generator, mock_llm_service
    ):
        """Should raise QueryValidationError when SQL doesn't start with SELECT."""
        mock_llm_service.generate.return_value = LLMResponse(
            response_type="sql",
            sql="INSERT INTO dataset VALUES (1, 2, 3)",
            answer=None,
        )

        with pytest.raises(QueryValidationError) as exc_info:
            sql_generator.generate_sql("Insert some data")

        assert "Could not generate a valid query" in exc_info.value.message

    def test_raises_error_when_sql_starts_with_with_clause(
        self, sql_generator, mock_llm_service
    ):
        """Should raise QueryValidationError for SQL starting with WITH (not SELECT)."""
        mock_llm_service.generate.return_value = LLMResponse(
            response_type="sql",
            sql="WITH cte AS (SELECT * FROM dataset) SELECT * FROM cte",
            answer=None,
        )

        with pytest.raises(QueryValidationError):
            sql_generator.generate_sql("Complex query")

    def test_propagates_llm_service_exceptions(self, sql_generator, mock_llm_service):
        """Should propagate exceptions raised by LLMService (e.g., timeout, unavailable)."""
        from app.exceptions import LLMTimeoutError

        mock_llm_service.generate.side_effect = LLMTimeoutError()

        with pytest.raises(LLMTimeoutError):
            sql_generator.generate_sql("Some prompt")

    def test_complex_select_query(self, sql_generator, mock_llm_service):
        """Should handle complex SELECT queries with subqueries, joins, etc."""
        complex_sql = (
            "SELECT region, SUM(sales) as total_sales "
            "FROM dataset WHERE year = 2023 GROUP BY region ORDER BY total_sales DESC LIMIT 10"
        )
        mock_llm_service.generate.return_value = LLMResponse(
            response_type="sql",
            sql=complex_sql,
            answer=None,
        )

        result = sql_generator.generate_sql("Top 10 regions by sales in 2023")

        assert result == complex_sql
