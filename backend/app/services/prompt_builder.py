"""Prompt builder service for constructing LLM prompts with dataset context."""

import pandas as pd

from app.models.chat_schemas import ChatMessage, ColumnSchema, QueryResult


class PromptBuilder:
    """Constructs LLM prompts with dataset context and conversation history."""

    def extract_schema(self, df: pd.DataFrame) -> list[ColumnSchema]:
        """Extract column names and inferred types from DataFrame.

        Maps pandas dtypes to simplified type categories:
        - "number": int64, float64, and other numeric types
        - "boolean": bool
        - "date": datetime64, timedelta64
        - "string": object, category, and all other types

        Returns all columns without truncation.
        """
        schema = []
        for col in df.columns:
            dtype = df[col].dtype
            if pd.api.types.is_bool_dtype(dtype):
                inferred_type = "boolean"
            elif pd.api.types.is_numeric_dtype(dtype):
                inferred_type = "number"
            elif pd.api.types.is_datetime64_any_dtype(dtype) or pd.api.types.is_timedelta64_dtype(dtype):
                inferred_type = "date"
            else:
                inferred_type = "string"
            schema.append(ColumnSchema(name=str(col), dtype=inferred_type))
        return schema

    def get_sample_rows(self, df: pd.DataFrame, max_rows: int = 5) -> list[dict]:
        """Get first N rows as list of dicts, where N = min(max_rows, len(df))."""
        n = min(max_rows, len(df))
        return df.head(n).to_dict(orient="records")

    def build_sql_prompt(
        self,
        schema: list[ColumnSchema],
        sample_rows: list[dict],
        total_row_count: int,
        history: list[ChatMessage],
        question: str,
    ) -> str:
        """Build prompt for SQL generation with schema context and history.

        Constructs a prompt that includes:
        - Dataset schema formatted as "column_name: data_type" lines
        - Total row count of the dataset
        - Sample rows for context
        - Up to 10 most recent conversation history messages (role + content only)
        - Grounding instruction
        - The user question
        """
        parts: list[str] = []

        # System instruction
        parts.append(
            "You are a SQL assistant. Generate a single SQL SELECT query to answer "
            "the user's question about a dataset. The table is named \"dataset\"."
        )

        # Grounding instruction
        parts.append(
            "You must answer only based on the data available in the dataset. "
            "Do not generate values, statistics, or facts that are not present in "
            "or derivable from the dataset."
        )

        # Schema section
        parts.append("Dataset schema:")
        for col in schema:
            parts.append(f"  {col.name}: {col.dtype}")

        # Total row count
        parts.append(f"\nTotal rows in dataset: {total_row_count}")

        # Sample rows
        if sample_rows:
            parts.append("\nSample rows:")
            for row in sample_rows:
                parts.append(f"  {row}")

        # Conversation history (up to 10 most recent, role + content only)
        recent_history = history[-10:] if len(history) > 10 else history
        if recent_history:
            parts.append("\nConversation history:")
            for msg in recent_history:
                parts.append(f"  {msg.role}: {msg.content}")

        # User question
        parts.append(f"\nQuestion: {question}")

        # Final instruction
        parts.append(
            "\nRespond with only a SQL SELECT query. Do not include explanations."
        )

        return "\n".join(parts)

    def build_answer_prompt(
        self,
        question: str,
        sql: str,
        results: QueryResult,
    ) -> str:
        """Build prompt for natural language answer generation from results.

        Includes an explicit grounding instruction that the model must not
        generate values, statistics, or facts that are not present in or
        derivable from the provided query results.
        """
        parts: list[str] = []

        # System instruction
        parts.append(
            "You are a data analyst assistant. Generate a clear, concise natural "
            "language answer to the user's question based on the query results below."
        )

        # Grounding instruction
        parts.append(
            "IMPORTANT: You must not generate values, statistics, or facts that are "
            "not present in or derivable from the provided query results. Only reference "
            "data that appears in the results or can be mathematically derived from them."
        )

        # User question
        parts.append(f"\nUser question: {question}")

        # SQL that was executed
        parts.append(f"\nSQL query executed:\n{sql}")

        # Query results
        parts.append(f"\nQuery results (columns: {results.columns}):")
        if results.rows:
            for row in results.rows:
                parts.append(f"  {row}")
        else:
            parts.append("  (no rows returned)")

        # Final instruction
        parts.append(
            "\nProvide a natural language answer that directly addresses the question "
            "using only the data shown above."
        )

        return "\n".join(parts)

    def build_retry_prompt(
        self,
        schema: list[ColumnSchema],
        history: list[ChatMessage],
        question: str,
        error_message: str,
    ) -> str:
        """Build prompt for SQL retry with previous error context.

        Includes the prior error message so the LLM can correct its SQL
        generation on the retry attempt.
        """
        parts: list[str] = []

        # System instruction
        parts.append(
            "You are a SQL assistant. Your previous SQL query failed. Generate a "
            "corrected SQL SELECT query to answer the user's question about a dataset. "
            "The table is named \"dataset\"."
        )

        # Error context
        parts.append(
            f"\nThe previous query failed with the following error:\n{error_message}"
        )

        parts.append(
            "\nPlease generate a corrected query that avoids this error."
        )

        # Schema section
        parts.append("\nDataset schema:")
        for col in schema:
            parts.append(f"  {col.name}: {col.dtype}")

        # Conversation history (up to 10 most recent, role + content only)
        recent_history = history[-10:] if len(history) > 10 else history
        if recent_history:
            parts.append("\nConversation history:")
            for msg in recent_history:
                parts.append(f"  {msg.role}: {msg.content}")

        # User question
        parts.append(f"\nQuestion: {question}")

        # Final instruction
        parts.append(
            "\nRespond with only a corrected SQL SELECT query. Do not include explanations."
        )

        return "\n".join(parts)
