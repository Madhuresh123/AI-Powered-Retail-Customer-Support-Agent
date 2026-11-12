"""Unit tests for PromptBuilder schema extraction and sample rows."""

import pandas as pd
import numpy as np
import pytest

from app.services.prompt_builder import PromptBuilder


@pytest.fixture
def builder():
    return PromptBuilder()


class TestExtractSchema:
    """Tests for PromptBuilder.extract_schema."""

    def test_numeric_columns(self, builder):
        """Integer and float columns map to 'number'."""
        df = pd.DataFrame({"int_col": [1, 2, 3], "float_col": [1.1, 2.2, 3.3]})
        schema = builder.extract_schema(df)
        assert len(schema) == 2
        assert schema[0].name == "int_col"
        assert schema[0].dtype == "number"
        assert schema[1].name == "float_col"
        assert schema[1].dtype == "number"

    def test_string_columns(self, builder):
        """Object dtype columns map to 'string'."""
        df = pd.DataFrame({"name": ["Alice", "Bob"], "city": ["NYC", "LA"]})
        schema = builder.extract_schema(df)
        assert all(col.dtype == "string" for col in schema)

    def test_boolean_columns(self, builder):
        """Boolean columns map to 'boolean'."""
        df = pd.DataFrame({"is_active": [True, False, True]})
        schema = builder.extract_schema(df)
        assert schema[0].dtype == "boolean"

    def test_datetime_columns(self, builder):
        """Datetime columns map to 'date'."""
        df = pd.DataFrame({"created_at": pd.to_datetime(["2024-01-01", "2024-02-01"])})
        schema = builder.extract_schema(df)
        assert schema[0].dtype == "date"

    def test_mixed_types(self, builder):
        """DataFrame with mixed types returns correct mappings."""
        df = pd.DataFrame({
            "id": [1, 2, 3],
            "name": ["a", "b", "c"],
            "active": [True, False, True],
            "created": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
            "score": [1.5, 2.5, 3.5],
        })
        schema = builder.extract_schema(df)
        assert len(schema) == 5
        type_map = {col.name: col.dtype for col in schema}
        assert type_map["id"] == "number"
        assert type_map["name"] == "string"
        assert type_map["active"] == "boolean"
        assert type_map["created"] == "date"
        assert type_map["score"] == "number"

    def test_all_columns_included(self, builder):
        """All columns are included without truncation."""
        cols = {f"col_{i}": [i] for i in range(50)}
        df = pd.DataFrame(cols)
        schema = builder.extract_schema(df)
        assert len(schema) == 50

    def test_empty_dataframe(self, builder):
        """Empty DataFrame with columns still returns schema."""
        df = pd.DataFrame({"a": pd.Series(dtype="int64"), "b": pd.Series(dtype="object")})
        schema = builder.extract_schema(df)
        assert len(schema) == 2
        assert schema[0].dtype == "number"
        assert schema[1].dtype == "string"

    def test_category_dtype_maps_to_string(self, builder):
        """Category dtype maps to 'string'."""
        df = pd.DataFrame({"status": pd.Categorical(["active", "inactive"])})
        schema = builder.extract_schema(df)
        assert schema[0].dtype == "string"


class TestGetSampleRows:
    """Tests for PromptBuilder.get_sample_rows."""

    def test_returns_first_5_rows(self, builder):
        """Returns first 5 rows for DataFrame with more than 5 rows."""
        df = pd.DataFrame({"x": range(20)})
        rows = builder.get_sample_rows(df)
        assert len(rows) == 5
        assert rows[0] == {"x": 0}
        assert rows[4] == {"x": 4}

    def test_returns_all_rows_if_less_than_max(self, builder):
        """Returns all rows when DataFrame has fewer than max_rows."""
        df = pd.DataFrame({"x": [10, 20, 30]})
        rows = builder.get_sample_rows(df)
        assert len(rows) == 3

    def test_empty_dataframe(self, builder):
        """Returns empty list for empty DataFrame."""
        df = pd.DataFrame({"x": pd.Series(dtype="int64")})
        rows = builder.get_sample_rows(df)
        assert rows == []

    def test_single_row(self, builder):
        """Returns single row for single-row DataFrame."""
        df = pd.DataFrame({"a": [42], "b": ["hello"]})
        rows = builder.get_sample_rows(df)
        assert len(rows) == 1
        assert rows[0] == {"a": 42, "b": "hello"}

    def test_custom_max_rows(self, builder):
        """Respects custom max_rows parameter."""
        df = pd.DataFrame({"x": range(100)})
        rows = builder.get_sample_rows(df, max_rows=3)
        assert len(rows) == 3

    def test_max_rows_greater_than_df_length(self, builder):
        """Returns all rows when max_rows exceeds DataFrame length."""
        df = pd.DataFrame({"x": [1, 2]})
        rows = builder.get_sample_rows(df, max_rows=10)
        assert len(rows) == 2

    def test_returns_list_of_dicts(self, builder):
        """Result is a list of dictionaries with column names as keys."""
        df = pd.DataFrame({"name": ["Alice", "Bob"], "age": [30, 25]})
        rows = builder.get_sample_rows(df)
        assert isinstance(rows, list)
        assert all(isinstance(r, dict) for r in rows)
        assert rows[0] == {"name": "Alice", "age": 30}


class TestBuildSqlPrompt:
    """Tests for PromptBuilder.build_sql_prompt."""

    def _make_schema(self):
        """Helper to create a sample schema."""
        from app.models.chat_schemas import ColumnSchema
        return [
            ColumnSchema(name="id", dtype="number"),
            ColumnSchema(name="name", dtype="string"),
            ColumnSchema(name="created_at", dtype="date"),
        ]

    def _make_message(self, role, content):
        """Helper to create a ChatMessage."""
        from app.models.chat_schemas import ChatMessage
        return ChatMessage(
            role=role,
            content=content,
            sql="SELECT 1" if role == "assistant" else None,
            data=[{"x": 1}] if role == "assistant" else None,
            timestamp="2024-01-15T10:00:00Z",
        )

    def test_includes_schema_formatted_as_name_colon_type(self, builder):
        """Schema is formatted as 'column_name: data_type' lines."""
        schema = self._make_schema()
        prompt = builder.build_sql_prompt(schema, [], 100, [], "What is the count?")
        assert "id: number" in prompt
        assert "name: string" in prompt
        assert "created_at: date" in prompt

    def test_includes_total_row_count(self, builder):
        """Prompt contains the total row count."""
        schema = self._make_schema()
        prompt = builder.build_sql_prompt(schema, [], 42567, [], "How many rows?")
        assert "42567" in prompt

    def test_includes_user_question(self, builder):
        """Prompt contains the user question."""
        schema = self._make_schema()
        question = "What is the average sales by region?"
        prompt = builder.build_sql_prompt(schema, [], 100, [], question)
        assert question in prompt

    def test_includes_grounding_instruction(self, builder):
        """Prompt includes explicit grounding instruction."""
        schema = self._make_schema()
        prompt = builder.build_sql_prompt(schema, [], 100, [], "test question")
        # Check for grounding keywords
        assert "only based on the data" in prompt.lower() or "not present in" in prompt.lower()

    def test_includes_sample_rows(self, builder):
        """Prompt includes sample rows when provided."""
        schema = self._make_schema()
        sample_rows = [{"id": 1, "name": "Alice", "created_at": "2024-01-01"}]
        prompt = builder.build_sql_prompt(schema, sample_rows, 100, [], "test")
        assert "Alice" in prompt

    def test_includes_history_role_and_content_only(self, builder):
        """History messages include role and content, exclude sql and data."""
        schema = self._make_schema()
        history = [
            self._make_message("user", "What is total sales?"),
            self._make_message("assistant", "The total sales is $5000."),
        ]
        prompt = builder.build_sql_prompt(schema, [], 100, history, "And by region?")
        # Role and content should be present
        assert "user" in prompt
        assert "What is total sales?" in prompt
        assert "assistant" in prompt
        assert "The total sales is $5000." in prompt
        # SQL and data from history should NOT appear in the prompt
        assert "SELECT 1" not in prompt

    def test_history_limited_to_10_messages(self, builder):
        """Only the 10 most recent messages are included."""
        schema = self._make_schema()
        # Create 15 messages
        history = []
        for i in range(15):
            role = "user" if i % 2 == 0 else "assistant"
            history.append(self._make_message(role, f"Message {i}"))

        prompt = builder.build_sql_prompt(schema, [], 100, history, "Next question")
        # Messages 0-4 should NOT be present (only 5-14 are the last 10)
        assert "Message 0" not in prompt
        assert "Message 4" not in prompt
        # Messages 5-14 should be present
        assert "Message 5" in prompt
        assert "Message 14" in prompt

    def test_history_chronological_order(self, builder):
        """History messages appear in chronological order (oldest first)."""
        schema = self._make_schema()
        history = [
            self._make_message("user", "First question"),
            self._make_message("assistant", "First answer"),
            self._make_message("user", "Second question"),
        ]
        prompt = builder.build_sql_prompt(schema, [], 100, history, "Third question")
        first_pos = prompt.index("First question")
        second_pos = prompt.index("Second question")
        assert first_pos < second_pos

    def test_no_history_still_produces_valid_prompt(self, builder):
        """Prompt is valid when no conversation history exists."""
        schema = self._make_schema()
        prompt = builder.build_sql_prompt(schema, [], 50, [], "Show all records")
        assert "Show all records" in prompt
        assert "50" in prompt
        # Should not have conversation history section header when empty
        # but prompt should still be complete and valid
        assert "Dataset schema:" in prompt

    def test_empty_schema_still_produces_prompt(self, builder):
        """Prompt is produced even with an empty schema list."""
        prompt = builder.build_sql_prompt([], [], 0, [], "What data is available?")
        assert "What data is available?" in prompt
        assert "0" in prompt


class TestBuildAnswerPrompt:
    """Tests for PromptBuilder.build_answer_prompt."""

    def _make_results(self, columns=None, rows=None):
        """Helper to create a QueryResult."""
        from app.models.chat_schemas import QueryResult
        if columns is None:
            columns = ["region", "total_sales"]
        if rows is None:
            rows = [{"region": "North", "total_sales": 45000}]
        return QueryResult(
            columns=columns,
            rows=rows,
        )

    def test_includes_grounding_instruction(self, builder):
        """Prompt contains explicit grounding instruction about not generating values."""
        results = self._make_results()
        prompt = builder.build_answer_prompt("What are total sales?", "SELECT *", results)
        lower_prompt = prompt.lower()
        assert "must not generate values" in lower_prompt or "not present in or derivable from" in lower_prompt

    def test_includes_user_question(self, builder):
        """Prompt contains the user question."""
        results = self._make_results()
        question = "What are total sales by region?"
        prompt = builder.build_answer_prompt(question, "SELECT *", results)
        assert question in prompt

    def test_includes_sql_query(self, builder):
        """Prompt contains the executed SQL query."""
        results = self._make_results()
        sql = "SELECT region, SUM(sales) FROM dataset GROUP BY region"
        prompt = builder.build_answer_prompt("What?", sql, results)
        assert sql in prompt

    def test_includes_query_results(self, builder):
        """Prompt contains the query results data."""
        results = self._make_results(
            columns=["name", "age"],
            rows=[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}],
        )
        prompt = builder.build_answer_prompt("Who?", "SELECT *", results)
        assert "Alice" in prompt
        assert "Bob" in prompt

    def test_includes_column_names(self, builder):
        """Prompt references the column names from results."""
        results = self._make_results(columns=["product", "revenue"])
        prompt = builder.build_answer_prompt("What?", "SELECT *", results)
        assert "product" in prompt
        assert "revenue" in prompt

    def test_empty_results_handled(self, builder):
        """Prompt handles empty result set gracefully."""
        results = self._make_results(columns=["x"], rows=[])
        prompt = builder.build_answer_prompt("Find x?", "SELECT x", results)
        assert "no rows returned" in prompt.lower()

    def test_grounding_instruction_mentions_query_results(self, builder):
        """Grounding instruction specifically mentions query results."""
        results = self._make_results()
        prompt = builder.build_answer_prompt("What?", "SELECT *", results)
        lower_prompt = prompt.lower()
        assert "query results" in lower_prompt


class TestBuildRetryPrompt:
    """Tests for PromptBuilder.build_retry_prompt."""

    def _make_schema(self):
        """Helper to create a sample schema."""
        from app.models.chat_schemas import ColumnSchema
        return [
            ColumnSchema(name="id", dtype="number"),
            ColumnSchema(name="name", dtype="string"),
        ]

    def _make_message(self, role, content):
        """Helper to create a ChatMessage."""
        from app.models.chat_schemas import ChatMessage
        return ChatMessage(
            role=role,
            content=content,
            sql=None,
            data=None,
            timestamp="2024-01-15T10:00:00Z",
        )

    def test_includes_error_message(self, builder):
        """Prompt contains the prior error message."""
        schema = self._make_schema()
        error_msg = "Table 'datset' does not exist. Did you mean 'dataset'?"
        prompt = builder.build_retry_prompt(schema, [], "Show all", error_msg)
        assert error_msg in prompt

    def test_includes_schema(self, builder):
        """Prompt contains the dataset schema."""
        schema = self._make_schema()
        prompt = builder.build_retry_prompt(schema, [], "Show all", "error occurred")
        assert "id: number" in prompt
        assert "name: string" in prompt

    def test_includes_user_question(self, builder):
        """Prompt contains the user question."""
        schema = self._make_schema()
        question = "What is the average score?"
        prompt = builder.build_retry_prompt(schema, [], question, "syntax error")
        assert question in prompt

    def test_includes_history(self, builder):
        """Prompt includes conversation history."""
        schema = self._make_schema()
        history = [
            self._make_message("user", "Previous question"),
            self._make_message("assistant", "Previous answer"),
        ]
        prompt = builder.build_retry_prompt(schema, history, "New question", "error")
        assert "Previous question" in prompt
        assert "Previous answer" in prompt

    def test_history_limited_to_10(self, builder):
        """Only the 10 most recent history messages are included."""
        schema = self._make_schema()
        history = [self._make_message("user", f"Msg {i}") for i in range(15)]
        prompt = builder.build_retry_prompt(schema, history, "question", "error")
        assert "Msg 0" not in prompt
        assert "Msg 4" not in prompt
        assert "Msg 5" in prompt
        assert "Msg 14" in prompt

    def test_no_history_still_valid(self, builder):
        """Prompt is valid with no conversation history."""
        schema = self._make_schema()
        prompt = builder.build_retry_prompt(schema, [], "Count rows", "timeout error")
        assert "Count rows" in prompt
        assert "timeout error" in prompt

    def test_instructs_correction(self, builder):
        """Prompt instructs the LLM to generate a corrected query."""
        schema = self._make_schema()
        prompt = builder.build_retry_prompt(schema, [], "test", "column not found")
        lower_prompt = prompt.lower()
        assert "corrected" in lower_prompt or "avoid this error" in lower_prompt
