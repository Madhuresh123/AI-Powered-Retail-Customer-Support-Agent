"""Unit tests for ChatService orchestration logic."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.exceptions import (
    QueryExecutionError,
    QueryValidationError,
)
from app.models.chat_schemas import (
    ChatDataResponse,
    ChatMessage,
    ChatResponse,
    ColumnSchema,
    LLMResponse,
    QueryResult,
)
from app.services.chat_service import ChatService


@pytest.fixture
def mock_dependencies():
    """Create mocked dependencies for ChatService."""
    dataset_service = MagicMock()
    prompt_builder = MagicMock()
    llm_service = MagicMock()
    query_executor = MagicMock()
    chat_history = MagicMock()

    return {
        "dataset_service": dataset_service,
        "prompt_builder": prompt_builder,
        "llm_service": llm_service,
        "query_executor": query_executor,
        "chat_history": chat_history,
    }


@pytest.fixture
def chat_service(mock_dependencies):
    """Create a ChatService with mocked dependencies."""
    return ChatService(**mock_dependencies)


@pytest.fixture
def sample_df():
    """Create a sample DataFrame for testing."""
    return pd.DataFrame(
        {"name": ["Alice", "Bob", "Charlie"], "age": [30, 25, 35], "city": ["NYC", "LA", "SF"]}
    )


@pytest.fixture
def sample_schema():
    """Sample schema returned by prompt builder."""
    return [
        ColumnSchema(name="name", dtype="string"),
        ColumnSchema(name="age", dtype="number"),
        ColumnSchema(name="city", dtype="string"),
    ]


class TestProcessQuestionSuccess:
    """Tests for successful question processing flow."""

    def test_full_orchestration_flow(self, chat_service, mock_dependencies, sample_df, sample_schema):
        """Test complete happy path: question -> SQL -> execution -> answer."""
        deps = mock_dependencies

        # Setup mocks
        deps["dataset_service"].get_dataframe.return_value = sample_df
        deps["chat_history"].get_recent_messages.return_value = []
        deps["prompt_builder"].extract_schema.return_value = sample_schema
        deps["prompt_builder"].get_sample_rows.return_value = [
            {"name": "Alice", "age": 30, "city": "NYC"}
        ]
        deps["prompt_builder"].build_sql_prompt.return_value = "SELECT AVG(age) FROM dataset"
        deps["llm_service"].generate.side_effect = [
            LLMResponse(response_type="sql", sql="SELECT AVG(age) FROM dataset"),
            LLMResponse(response_type="answer", answer="The average age is 30."),
        ]
        deps["query_executor"].validate_query.return_value = None
        deps["query_executor"].execute.return_value = QueryResult(
            columns=["avg_age"], rows=[{"avg_age": 30.0}]
        )
        deps["prompt_builder"].build_answer_prompt.return_value = "answer prompt"

        result = chat_service.process_question("dataset-123", "What is the average age?")

        assert isinstance(result, ChatResponse)
        assert result.answer == "The average age is 30."
        assert result.sql == "SELECT AVG(age) FROM dataset"
        assert result.data is not None
        assert result.data.columns == ["avg_age"]
        assert result.data.rows == [{"avg_age": 30.0}]
        assert result.timestamp is not None

    def test_answer_truncated_to_2000_chars(self, chat_service, mock_dependencies, sample_df, sample_schema):
        """Test answer is truncated to 2000 characters max."""
        deps = mock_dependencies

        deps["dataset_service"].get_dataframe.return_value = sample_df
        deps["chat_history"].get_recent_messages.return_value = []
        deps["prompt_builder"].extract_schema.return_value = sample_schema
        deps["prompt_builder"].get_sample_rows.return_value = []
        deps["prompt_builder"].build_sql_prompt.return_value = "prompt"
        long_answer = "x" * 3000
        deps["llm_service"].generate.side_effect = [
            LLMResponse(response_type="sql", sql="SELECT * FROM dataset"),
            LLMResponse(response_type="answer", answer=long_answer),
        ]
        deps["query_executor"].validate_query.return_value = None
        deps["query_executor"].execute.return_value = QueryResult(
            columns=["name"], rows=[{"name": "Alice"}]
        )
        deps["prompt_builder"].build_answer_prompt.return_value = "answer prompt"

        result = chat_service.process_question("dataset-123", "Show all")

        assert len(result.answer) == 2000

    def test_response_rows_limited_to_100(self, chat_service, mock_dependencies, sample_df, sample_schema):
        """Test response data.rows is limited to 100 entries."""
        deps = mock_dependencies

        deps["dataset_service"].get_dataframe.return_value = sample_df
        deps["chat_history"].get_recent_messages.return_value = []
        deps["prompt_builder"].extract_schema.return_value = sample_schema
        deps["prompt_builder"].get_sample_rows.return_value = []
        deps["prompt_builder"].build_sql_prompt.return_value = "prompt"

        # Return 200 rows from query executor
        many_rows = [{"id": i} for i in range(200)]
        deps["llm_service"].generate.side_effect = [
            LLMResponse(response_type="sql", sql="SELECT * FROM dataset"),
            LLMResponse(response_type="answer", answer="Here are results."),
        ]
        deps["query_executor"].validate_query.return_value = None
        deps["query_executor"].execute.return_value = QueryResult(
            columns=["id"], rows=many_rows
        )
        deps["prompt_builder"].build_answer_prompt.return_value = "answer prompt"

        result = chat_service.process_question("dataset-123", "Show all")

        assert result.data is not None
        assert len(result.data.rows) == 100

    def test_persists_user_and_assistant_messages(self, chat_service, mock_dependencies, sample_df, sample_schema):
        """Test that both user and assistant messages are persisted on success."""
        deps = mock_dependencies

        deps["dataset_service"].get_dataframe.return_value = sample_df
        deps["chat_history"].get_recent_messages.return_value = []
        deps["prompt_builder"].extract_schema.return_value = sample_schema
        deps["prompt_builder"].get_sample_rows.return_value = []
        deps["prompt_builder"].build_sql_prompt.return_value = "prompt"
        deps["llm_service"].generate.side_effect = [
            LLMResponse(response_type="sql", sql="SELECT * FROM dataset"),
            LLMResponse(response_type="answer", answer="Answer text."),
        ]
        deps["query_executor"].validate_query.return_value = None
        deps["query_executor"].execute.return_value = QueryResult(
            columns=["name"], rows=[{"name": "Alice"}]
        )
        deps["prompt_builder"].build_answer_prompt.return_value = "answer prompt"

        chat_service.process_question("dataset-123", "Show names")

        # Should have called save_message twice (user + assistant)
        assert deps["chat_history"].save_message.call_count == 2
        calls = deps["chat_history"].save_message.call_args_list

        # First call: user message
        user_msg = calls[0][0][1]
        assert user_msg.role == "user"
        assert user_msg.content == "Show names"

        # Second call: assistant message
        assistant_msg = calls[1][0][1]
        assert assistant_msg.role == "assistant"
        assert assistant_msg.content == "Answer text."
        assert assistant_msg.sql == "SELECT * FROM dataset"


class TestRetryLogic:
    """Tests for SQL execution retry logic."""

    def test_retry_on_first_failure_then_success(self, chat_service, mock_dependencies, sample_df, sample_schema):
        """Test retry once on first SQL execution failure."""
        deps = mock_dependencies

        deps["dataset_service"].get_dataframe.return_value = sample_df
        deps["chat_history"].get_recent_messages.return_value = []
        deps["prompt_builder"].extract_schema.return_value = sample_schema
        deps["prompt_builder"].get_sample_rows.return_value = []
        deps["prompt_builder"].build_sql_prompt.return_value = "prompt"
        deps["prompt_builder"].build_retry_prompt.return_value = "retry prompt"
        deps["prompt_builder"].build_answer_prompt.return_value = "answer prompt"

        # First SQL generation succeeds
        deps["llm_service"].generate.side_effect = [
            LLMResponse(response_type="sql", sql="SELECT bad FROM dataset"),
            LLMResponse(response_type="sql", sql="SELECT name FROM dataset"),
            LLMResponse(response_type="answer", answer="Retry succeeded."),
        ]

        # First execution fails, second succeeds
        deps["query_executor"].validate_query.return_value = None
        deps["query_executor"].execute.side_effect = [
            QueryExecutionError("Column 'bad' not found"),
            QueryResult(columns=["name"], rows=[{"name": "Alice"}]),
        ]

        result = chat_service.process_question("dataset-123", "Show names")

        assert result.answer == "Retry succeeded."
        assert result.sql == "SELECT name FROM dataset"

    def test_both_attempts_fail_returns_error_response(self, chat_service, mock_dependencies, sample_df, sample_schema):
        """Test error response when both SQL attempts fail."""
        deps = mock_dependencies

        deps["dataset_service"].get_dataframe.return_value = sample_df
        deps["chat_history"].get_recent_messages.return_value = []
        deps["prompt_builder"].extract_schema.return_value = sample_schema
        deps["prompt_builder"].get_sample_rows.return_value = []
        deps["prompt_builder"].build_sql_prompt.return_value = "prompt"
        deps["prompt_builder"].build_retry_prompt.return_value = "retry prompt"

        # Both SQL generations succeed but both executions fail
        deps["llm_service"].generate.side_effect = [
            LLMResponse(response_type="sql", sql="SELECT bad1 FROM dataset"),
            LLMResponse(response_type="sql", sql="SELECT bad2 FROM dataset"),
        ]
        deps["query_executor"].validate_query.return_value = None
        deps["query_executor"].execute.side_effect = [
            QueryExecutionError("Error 1"),
            QueryExecutionError("Error 2"),
        ]

        result = chat_service.process_question("dataset-123", "Bad question")

        assert result.sql is None
        assert result.data is None
        assert "Could not generate a valid query" in result.answer


class TestEmptyResults:
    """Tests for empty result set handling."""

    def test_empty_results_returns_no_data_message(self, chat_service, mock_dependencies, sample_df, sample_schema):
        """Test graceful handling of empty result sets."""
        deps = mock_dependencies

        deps["dataset_service"].get_dataframe.return_value = sample_df
        deps["chat_history"].get_recent_messages.return_value = []
        deps["prompt_builder"].extract_schema.return_value = sample_schema
        deps["prompt_builder"].get_sample_rows.return_value = []
        deps["prompt_builder"].build_sql_prompt.return_value = "prompt"
        deps["llm_service"].generate.side_effect = [
            LLMResponse(response_type="sql", sql="SELECT * FROM dataset WHERE age > 100"),
        ]
        deps["query_executor"].validate_query.return_value = None
        deps["query_executor"].execute.return_value = QueryResult(columns=[], rows=[])

        result = chat_service.process_question("dataset-123", "Who is older than 100?")

        assert "No matching data" in result.answer
        assert result.sql == "SELECT * FROM dataset WHERE age > 100"


class TestUnmappableQuestions:
    """Tests for questions that can't be mapped to SQL."""

    def test_unmappable_question_returns_explanation(self, chat_service, mock_dependencies, sample_df, sample_schema):
        """Test handling when SQL generation fails due to unmappable question."""
        deps = mock_dependencies

        deps["dataset_service"].get_dataframe.return_value = sample_df
        deps["chat_history"].get_recent_messages.return_value = []
        deps["prompt_builder"].extract_schema.return_value = sample_schema
        deps["prompt_builder"].get_sample_rows.return_value = []
        deps["prompt_builder"].build_sql_prompt.return_value = "prompt"

        # SQLGenerator raises QueryValidationError (can't generate valid SQL)
        deps["llm_service"].generate.return_value = LLMResponse(
            response_type="answer", sql=None, answer="cannot do this"
        )

        result = chat_service.process_question("dataset-123", "What is the meaning of life?")

        assert "couldn't generate a valid query" in result.answer
        assert result.sql is None
        assert result.data is None


class TestConversationHistory:
    """Tests for conversation history integration."""

    def test_history_passed_to_prompt_builder(self, chat_service, mock_dependencies, sample_df, sample_schema):
        """Test that recent history is passed to prompt builder."""
        deps = mock_dependencies

        history_messages = [
            ChatMessage(role="user", content="Previous question", timestamp="2024-01-01T00:00:00Z"),
            ChatMessage(role="assistant", content="Previous answer", timestamp="2024-01-01T00:00:01Z"),
        ]

        deps["dataset_service"].get_dataframe.return_value = sample_df
        deps["chat_history"].get_recent_messages.return_value = history_messages
        deps["prompt_builder"].extract_schema.return_value = sample_schema
        deps["prompt_builder"].get_sample_rows.return_value = []
        deps["prompt_builder"].build_sql_prompt.return_value = "prompt"
        deps["prompt_builder"].build_answer_prompt.return_value = "answer prompt"
        deps["llm_service"].generate.side_effect = [
            LLMResponse(response_type="sql", sql="SELECT * FROM dataset"),
            LLMResponse(response_type="answer", answer="Follow-up answer."),
        ]
        deps["query_executor"].validate_query.return_value = None
        deps["query_executor"].execute.return_value = QueryResult(
            columns=["name"], rows=[{"name": "Alice"}]
        )

        chat_service.process_question("dataset-123", "Follow-up question")

        # Verify history was passed to build_sql_prompt
        call_kwargs = deps["prompt_builder"].build_sql_prompt.call_args
        assert call_kwargs[1]["history"] == history_messages
