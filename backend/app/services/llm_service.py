"""LLM Service for interfacing with OpenRouter (OpenAI-compatible) API."""

import os

import httpx

from app.exceptions import (
    ConfigurationError,
    LLMParseError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.models.chat_schemas import LLMResponse


class LLMService:
    """Interface to OpenRouter LLM provider for SQL generation and answer generation."""

    TIMEOUT_SECONDS = 60

    def __init__(self) -> None:
        """
        Load configuration from environment variables:
        - LLM_API_URL: LLM provider endpoint (OpenRouter chat completions URL)
        - LLM_API_KEY: API authentication key
        - LLM_MODEL: Model identifier (optional, defaults to deepseek/deepseek-chat-v3-0324:free)

        Raises:
            ConfigurationError: If LLM_API_URL or LLM_API_KEY is missing or empty.
        """
        self.api_url = os.environ.get("LLM_API_URL", "").strip()
        self.api_key = os.environ.get("LLM_API_KEY", "").strip()
        self.model = os.environ.get(
            "LLM_MODEL", "deepseek/deepseek-chat-v3-0324:free"
        ).strip()

        if not self.api_url:
            raise ConfigurationError(
                "LLM_API_URL environment variable is missing or empty"
            )
        if not self.api_key:
            raise ConfigurationError(
                "LLM_API_KEY environment variable is missing or empty"
            )

    def generate(self, prompt: str) -> LLMResponse:
        """
        Send prompt to LLM via OpenAI-compatible chat completions API.

        The prompt is sent as a system+user message pair. The response text
        is then parsed to determine if it contains SQL or a natural language answer.

        Returns:
            LLMResponse with either sql or answer field populated.

        Raises:
            LLMUnavailableError: If provider unreachable or returns non-2xx.
            LLMTimeoutError: If no response within 60 seconds.
            LLMParseError: If response body cannot be parsed.
        """
        import time

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": 0.1,
            "max_tokens": 2048,
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=self.TIMEOUT_SECONDS) as client:
                    response = client.post(
                        self.api_url,
                        json=payload,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "http://localhost:3000",
                            "X-Title": "Data Insight",
                        },
                    )
            except httpx.TimeoutException:
                raise LLMTimeoutError("AI service request timed out")
            except httpx.ConnectError:
                raise LLMUnavailableError("AI service is temporarily unavailable")
            except httpx.HTTPError:
                raise LLMUnavailableError("AI service is temporarily unavailable")

            # Handle rate limiting with retry
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5  # 5s, 10s, 15s
                    time.sleep(wait_time)
                    continue
                else:
                    raise LLMUnavailableError(
                        "AI service is rate limited. Please wait a moment and try again."
                    )

            if response.status_code < 200 or response.status_code >= 300:
                raise LLMUnavailableError(
                    f"AI service returned HTTP {response.status_code}"
                )

            break

        return self._parse_response(response)

    def _parse_response(self, response: httpx.Response) -> LLMResponse:
        """
        Parse OpenAI-compatible chat completions response.

        Extracts the assistant's message content, then determines if it's
        SQL (starts with SELECT) or a natural language answer.

        Raises:
            LLMParseError: If response body cannot be parsed.
        """
        try:
            data = response.json()
        except Exception:
            raise LLMParseError("AI service returned an invalid response")

        if not isinstance(data, dict):
            raise LLMParseError("AI service returned an invalid response")

        # Extract content from OpenAI chat completions format
        choices = data.get("choices")
        if not choices or not isinstance(choices, list) or len(choices) == 0:
            raise LLMParseError("AI service returned an invalid response")

        message = choices[0].get("message", {})
        content = message.get("content", "").strip()

        if not content:
            raise LLMParseError("AI service returned an invalid response")

        # Try to extract SQL from the response
        sql = self._extract_sql(content)
        if sql:
            return LLMResponse(
                response_type="sql",
                sql=sql,
                answer=None,
            )
        else:
            return LLMResponse(
                response_type="answer",
                sql=None,
                answer=content,
            )

    def _extract_sql(self, content: str) -> str | None:
        """
        Try to extract a SQL SELECT query from the LLM response content.

        Handles multiple formats:
        - Plain SQL starting with SELECT
        - SQL wrapped in ```sql ... ``` code blocks
        - SQL wrapped in ``` ... ``` code blocks
        - Text followed by a code block containing SQL
        - Content with <think>...</think> reasoning blocks before SQL

        Returns the SQL string if found, or None if content is not SQL.
        """
        import re

        # Remove <think>...</think> blocks (reasoning models)
        cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        # Try to find SQL in a code block first (```sql ... ``` or ``` ... ```)
        code_block_match = re.search(
            r"```(?:sql)?\s*\n?(.*?)\n?\s*```", cleaned, re.DOTALL
        )
        if code_block_match:
            sql_candidate = code_block_match.group(1).strip()
            if sql_candidate.upper().startswith("SELECT"):
                return sql_candidate

        # Try plain content (after stripping markdown)
        plain = cleaned
        if plain.startswith("```sql"):
            plain = plain[6:]
        elif plain.startswith("```"):
            plain = plain[3:]
        if plain.endswith("```"):
            plain = plain[:-3]
        plain = plain.strip()

        if plain.upper().startswith("SELECT"):
            return plain

        # Try to find a SELECT statement anywhere in the text
        select_match = re.search(
            r"(SELECT\b.*?)(?:;|\Z)", cleaned, re.DOTALL | re.IGNORECASE
        )
        if select_match:
            sql_candidate = select_match.group(1).strip()
            # Only use if it looks substantial (not just the word "select" in prose)
            if len(sql_candidate) > 10 and "FROM" in sql_candidate.upper():
                # Remove trailing semicolons
                return sql_candidate.rstrip(";").strip()

        return None
