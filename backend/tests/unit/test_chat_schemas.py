"""Unit tests for chat Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.models.chat_schemas import (
    ChatDataResponse,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ColumnSchema,
    LLMResponse,
    QueryResult,
)


class TestChatRequest:
    """Tests for ChatRequest schema."""

    def test_valid_request(self):
        req = ChatRequest(dataset_id="ds-123", question="What is the average?")
        assert req.dataset_id == "ds-123"
        assert req.question == "What is the average?"

    def test_missing_dataset_id(self):
        with pytest.raises(ValidationError):
            ChatRequest(question="What is the average?")

    def test_missing_question(self):
        with pytest.raises(ValidationError):
            ChatRequest(dataset_id="ds-123")

    def test_empty_question_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(dataset_id="ds-123", question="")

    def test_question_max_length(self):
        long_question = "a" * 1001
        with pytest.raises(ValidationError):
            ChatRequest(dataset_id="ds-123", question=long_question)

    def test_question_at_max_length(self):
        question = "a" * 1000
        req = ChatRequest(dataset_id="ds-123", question=question)
        assert len(req.question) == 1000


class TestChatResponse:
    """Tests for ChatResponse schema."""

    def test_valid_response_with_data(self):
        resp = ChatResponse(
            answer="The average is 42.",
            sql="SELECT AVG(value) FROM dataset",
            data=ChatDataResponse(columns=["avg"], rows=[{"avg": 42}]),
            timestamp="2024-01-15T10:30:00Z",
        )
        assert resp.answer == "The average is 42."
        assert resp.sql == "SELECT AVG(value) FROM dataset"
        assert resp.data.columns == ["avg"]
        assert resp.timestamp == "2024-01-15T10:30:00Z"

    def test_valid_response_without_optional_fields(self):
        resp = ChatResponse(
            answer="No data found.",
            timestamp="2024-01-15T10:30:00Z",
        )
        assert resp.sql is None
        assert resp.data is None

    def test_answer_max_length(self):
        with pytest.raises(ValidationError):
            ChatResponse(
                answer="a" * 2001,
                timestamp="2024-01-15T10:30:00Z",
            )

    def test_answer_at_max_length(self):
        resp = ChatResponse(
            answer="a" * 2000,
            timestamp="2024-01-15T10:30:00Z",
        )
        assert len(resp.answer) == 2000


class TestChatMessage:
    """Tests for ChatMessage schema."""

    def test_user_message(self):
        msg = ChatMessage(
            role="user",
            content="What are the top products?",
            timestamp="2024-01-15T10:30:00Z",
        )
        assert msg.role == "user"
        assert msg.sql is None
        assert msg.data is None

    def test_assistant_message_with_sql_and_data(self):
        msg = ChatMessage(
            role="assistant",
            content="The top product is Widget A.",
            sql="SELECT name FROM dataset ORDER BY sales DESC LIMIT 1",
            data=[{"name": "Widget A", "sales": 1000}],
            timestamp="2024-01-15T10:30:02Z",
        )
        assert msg.role == "assistant"
        assert msg.sql is not None
        assert msg.data is not None

    def test_content_max_length(self):
        with pytest.raises(ValidationError):
            ChatMessage(
                role="user",
                content="a" * 4097,
                timestamp="2024-01-15T10:30:00Z",
            )


class TestColumnSchema:
    """Tests for ColumnSchema schema."""

    def test_valid_column_schema(self):
        col = ColumnSchema(name="age", dtype="number")
        assert col.name == "age"
        assert col.dtype == "number"


class TestQueryResult:
    """Tests for QueryResult schema."""

    def test_valid_query_result(self):
        result = QueryResult(
            columns=["name", "value"],
            rows=[{"name": "A", "value": 1}, {"name": "B", "value": 2}],
        )
        assert len(result.columns) == 2
        assert len(result.rows) == 2

    def test_empty_result(self):
        result = QueryResult(columns=[], rows=[])
        assert result.columns == []
        assert result.rows == []


class TestLLMResponse:
    """Tests for LLMResponse schema."""

    def test_sql_response(self):
        resp = LLMResponse(
            response_type="sql",
            sql="SELECT * FROM dataset",
        )
        assert resp.response_type == "sql"
        assert resp.sql == "SELECT * FROM dataset"
        assert resp.answer is None

    def test_answer_response(self):
        resp = LLMResponse(
            response_type="answer",
            answer="The total is 500.",
        )
        assert resp.response_type == "answer"
        assert resp.sql is None
        assert resp.answer == "The total is 500."
