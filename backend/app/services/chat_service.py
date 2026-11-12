"""Chat service orchestrating the full question-to-answer flow."""

from datetime import datetime, timezone

from app.exceptions import (
    QueryExecutionError,
    QueryValidationError,
)
from app.models.chat_schemas import (
    ChatDataResponse,
    ChatMessage,
    ChatResponse,
)
from app.services.chat_history import ChatHistory
from app.services.dataset_service import DatasetService
from app.services.llm_service import LLMService
from app.services.prompt_builder import PromptBuilder
from app.services.query_executor import QueryExecutor
from app.services.sql_generator import SQLGenerator


class ChatService:
    """Orchestrates the full chat flow from question to answer.

    Coordinates between DatasetService, PromptBuilder, LLMService (via SQLGenerator),
    QueryExecutor, and ChatHistory to process natural language questions about datasets.
    """

    MAX_ANSWER_LENGTH = 2000
    MAX_RESPONSE_ROWS = 100
    HISTORY_CONTEXT_LIMIT = 10

    def __init__(
        self,
        dataset_service: DatasetService,
        prompt_builder: PromptBuilder,
        llm_service: LLMService,
        query_executor: QueryExecutor,
        chat_history: ChatHistory,
    ) -> None:
        self.dataset_service = dataset_service
        self.prompt_builder = prompt_builder
        self.llm_service = llm_service
        self.query_executor = query_executor
        self.chat_history = chat_history
        self.sql_generator = SQLGenerator(llm_service)

    def process_question(self, dataset_id: str, question: str) -> ChatResponse:
        """Full orchestration flow for processing a chat question.

        Steps:
        1. Load dataset DataFrame via DatasetService
        2. Retrieve up to 10 recent conversation messages
        3. Extract schema and sample rows via PromptBuilder
        4. Build SQL prompt and call LLM via SQLGenerator
        5. Validate and execute SQL (retry once on failure with error context)
        6. Build answer prompt with query results and call LLM
        7. Truncate answer to 2000 chars
        8. Limit response data rows to 100
        9. Persist user and assistant messages to history
        10. Return ChatResponse with answer, sql, data, timestamp

        Args:
            dataset_id: The UUID of the dataset to query.
            question: The natural language question from the user.

        Returns:
            ChatResponse with answer, sql, data, and timestamp.

        Raises:
            DatasetNotFoundError: If dataset_id doesn't exist.
            LLMUnavailableError: If LLM provider is unreachable.
            LLMTimeoutError: If LLM does not respond in time.
            QueryValidationError: If generated SQL contains prohibited keywords.
        """
        # 1. Load dataset DataFrame
        df = self.dataset_service.get_dataframe(dataset_id)

        # 2. Retrieve up to 10 recent conversation messages
        history = self.chat_history.get_recent_messages(
            dataset_id, limit=self.HISTORY_CONTEXT_LIMIT
        )

        # 3. Extract schema and sample rows
        schema = self.prompt_builder.extract_schema(df)
        sample_rows = self.prompt_builder.get_sample_rows(df)
        total_row_count = len(df)

        # 4. Build SQL prompt and call LLM
        sql_prompt = self.prompt_builder.build_sql_prompt(
            schema=schema,
            sample_rows=sample_rows,
            total_row_count=total_row_count,
            history=history,
            question=question,
        )

        try:
            sql = self.sql_generator.generate_sql(sql_prompt)
        except QueryValidationError:
            # Question cannot be mapped to a valid SQL query
            return self._build_unmappable_response(dataset_id, question)

        # 5. Validate and execute SQL (retry once on failure)
        query_result = self._execute_with_retry(
            df=df,
            sql=sql,
            schema=schema,
            history=history,
            question=question,
            dataset_id=dataset_id,
        )

        if query_result is None:
            # Both attempts failed — return error response
            return self._build_execution_error_response(dataset_id, question)

        sql_used = sql if query_result.get("retried_sql") is None else query_result["retried_sql"]
        result = query_result["result"]

        # Handle empty result sets
        if not result.rows:
            return self._build_empty_result_response(
                dataset_id, question, sql_used
            )

        # 6. Build answer prompt with query results and call LLM
        answer_prompt = self.prompt_builder.build_answer_prompt(
            question=question,
            sql=sql_used,
            results=result,
        )

        llm_response = self.llm_service.generate(answer_prompt)
        answer = llm_response.answer or ""

        # 7. Truncate answer to 2000 chars
        if len(answer) > self.MAX_ANSWER_LENGTH:
            answer = answer[: self.MAX_ANSWER_LENGTH]

        # 8. Limit response data rows to 100
        response_rows = result.rows[: self.MAX_RESPONSE_ROWS]

        # Build response
        timestamp = datetime.now(timezone.utc).isoformat()

        data = ChatDataResponse(
            columns=result.columns,
            rows=response_rows,
        )

        response = ChatResponse(
            answer=answer,
            sql=sql_used,
            data=data,
            timestamp=timestamp,
        )

        # 9. Persist user and assistant messages to history
        self._persist_messages(
            dataset_id=dataset_id,
            question=question,
            answer=answer,
            sql=sql_used,
            response_rows=response_rows,
            timestamp=timestamp,
        )

        # 10. Return ChatResponse
        return response

    def _execute_with_retry(
        self,
        df,
        sql: str,
        schema,
        history,
        question: str,
        dataset_id: str,
    ) -> dict | None:
        """Execute SQL with one retry on failure.

        Returns a dict with 'result' (QueryResult) and optionally 'retried_sql',
        or None if both attempts fail.
        """
        # First attempt
        error_message = ""
        try:
            self.query_executor.validate_query(sql)
            result = self.query_executor.execute(df, sql)
            return {"result": result, "retried_sql": None}
        except (QueryExecutionError, QueryValidationError) as e:
            error_message = str(e)

        # Retry once with error context

        retry_prompt = self.prompt_builder.build_retry_prompt(
            schema=schema,
            history=history,
            question=question,
            error_message=error_message,
        )

        try:
            retried_sql = self.sql_generator.generate_sql(retry_prompt)
        except QueryValidationError:
            return None

        try:
            self.query_executor.validate_query(retried_sql)
            result = self.query_executor.execute(df, retried_sql)
            return {"result": result, "retried_sql": retried_sql}
        except (QueryExecutionError, QueryValidationError):
            return None

    def _build_unmappable_response(
        self, dataset_id: str, question: str
    ) -> ChatResponse:
        """Build response when question can't be mapped to SQL."""
        timestamp = datetime.now(timezone.utc).isoformat()
        answer = (
            "I couldn't generate a valid query for your question. "
            "The question may reference columns or concepts that don't match "
            "the available data in this dataset."
        )

        # Persist messages
        self._persist_messages(
            dataset_id=dataset_id,
            question=question,
            answer=answer,
            sql=None,
            response_rows=None,
            timestamp=timestamp,
        )

        return ChatResponse(
            answer=answer,
            sql=None,
            data=None,
            timestamp=timestamp,
        )

    def _build_empty_result_response(
        self, dataset_id: str, question: str, sql: str
    ) -> ChatResponse:
        """Build response when query returns empty results."""
        timestamp = datetime.now(timezone.utc).isoformat()
        answer = (
            "No matching data was found in the dataset for your question. "
            "The query executed successfully but returned no results."
        )

        data = ChatDataResponse(columns=[], rows=[])

        # Persist messages
        self._persist_messages(
            dataset_id=dataset_id,
            question=question,
            answer=answer,
            sql=sql,
            response_rows=[],
            timestamp=timestamp,
        )

        return ChatResponse(
            answer=answer,
            sql=sql,
            data=data,
            timestamp=timestamp,
        )

    def _build_execution_error_response(
        self, dataset_id: str, question: str
    ) -> ChatResponse:
        """Build response when SQL execution fails after retry."""
        timestamp = datetime.now(timezone.utc).isoformat()
        answer = (
            "Could not generate a valid query for your question. "
            "Please try rephrasing your question or ask about different aspects of the data."
        )

        # Persist messages
        self._persist_messages(
            dataset_id=dataset_id,
            question=question,
            answer=answer,
            sql=None,
            response_rows=None,
            timestamp=timestamp,
        )

        return ChatResponse(
            answer=answer,
            sql=None,
            data=None,
            timestamp=timestamp,
        )

    def _persist_messages(
        self,
        dataset_id: str,
        question: str,
        answer: str,
        sql: str | None,
        response_rows: list[dict] | None,
        timestamp: str,
    ) -> None:
        """Persist user and assistant messages to chat history."""
        # Save user message
        user_message = ChatMessage(
            role="user",
            content=question,
            sql=None,
            data=None,
            timestamp=timestamp,
        )
        self.chat_history.save_message(dataset_id, user_message)

        # Save assistant message
        assistant_message = ChatMessage(
            role="assistant",
            content=answer,
            sql=sql,
            data=response_rows,
            timestamp=timestamp,
        )
        self.chat_history.save_message(dataset_id, assistant_message)
