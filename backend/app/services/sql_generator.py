"""SQL Generator service for converting natural language prompts to SQL via LLM."""

from app.exceptions import QueryValidationError
from app.models.chat_schemas import LLMResponse
from app.services.llm_service import LLMService


class SQLGenerator:
    """Thin wrapper around LLM_Service for SQL generation with validation."""

    def __init__(self, llm_service: LLMService) -> None:
        self.llm_service = llm_service

    def generate_sql(self, prompt: str) -> str:
        """
        Call LLM and extract SQL from response.
        Validates the response contains a SELECT statement.

        Args:
            prompt: The fully constructed prompt for SQL generation.

        Returns:
            A validated SQL SELECT query string.

        Raises:
            QueryValidationError: If LLM returns a non-SQL response or
                the SQL does not start with SELECT.
            LLMUnavailableError: If LLM provider is unreachable.
            LLMTimeoutError: If LLM does not respond in time.
            LLMParseError: If LLM response cannot be parsed.
        """
        response: LLMResponse = self.llm_service.generate(prompt)

        if response.response_type != "sql" or not response.sql:
            raise QueryValidationError(
                "Could not generate a valid query for your question"
            )

        sql = response.sql.strip()

        if not sql.upper().startswith("SELECT"):
            raise QueryValidationError(
                "Could not generate a valid query for your question"
            )

        return sql
