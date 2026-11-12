"""Unit tests for LLMService."""

from unittest.mock import patch, MagicMock

import httpx
import pytest

from app.exceptions import (
    ConfigurationError,
    LLMParseError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.models.chat_schemas import LLMResponse


class TestLLMServiceConfiguration:
    """Test configuration validation on init."""

    def test_missing_llm_api_url_raises_configuration_error(self):
        """ConfigurationError raised when LLM_API_URL is missing."""
        env = {"LLM_API_KEY": "test-key"}
        with patch.dict("os.environ", env, clear=True):
            with pytest.raises(ConfigurationError, match="LLM_API_URL"):
                from app.services.llm_service import LLMService
                LLMService()

    def test_empty_llm_api_url_raises_configuration_error(self):
        """ConfigurationError raised when LLM_API_URL is empty."""
        env = {"LLM_API_URL": "   ", "LLM_API_KEY": "test-key"}
        with patch.dict("os.environ", env, clear=True):
            with pytest.raises(ConfigurationError, match="LLM_API_URL"):
                from app.services.llm_service import LLMService
                LLMService()

    def test_missing_llm_api_key_raises_configuration_error(self):
        """ConfigurationError raised when LLM_API_KEY is missing."""
        env = {"LLM_API_URL": "http://llm.example.com/api"}
        with patch.dict("os.environ", env, clear=True):
            with pytest.raises(ConfigurationError, match="LLM_API_KEY"):
                from app.services.llm_service import LLMService
                LLMService()

    def test_empty_llm_api_key_raises_configuration_error(self):
        """ConfigurationError raised when LLM_API_KEY is empty."""
        env = {"LLM_API_URL": "http://llm.example.com/api", "LLM_API_KEY": "  "}
        with patch.dict("os.environ", env, clear=True):
            with pytest.raises(ConfigurationError, match="LLM_API_KEY"):
                from app.services.llm_service import LLMService
                LLMService()

    def test_valid_configuration_succeeds(self):
        """No error raised when both env vars are set."""
        env = {"LLM_API_URL": "http://llm.example.com/api", "LLM_API_KEY": "test-key"}
        with patch.dict("os.environ", env, clear=True):
            from app.services.llm_service import LLMService
            service = LLMService()
            assert service.api_url == "http://llm.example.com/api"
            assert service.api_key == "test-key"


class TestLLMServiceGenerate:
    """Test the generate method."""

    def _create_service(self):
        """Create an LLMService with valid config."""
        env = {
            "LLM_API_URL": "http://llm.example.com/api",
            "LLM_API_KEY": "test-key",
            "LLM_MODEL": "test-model",
        }
        with patch.dict("os.environ", env, clear=True):
            from app.services.llm_service import LLMService
            return LLMService()

    def _make_chat_response(self, content: str) -> dict:
        """Build an OpenAI-compatible chat completions response."""
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": content,
                    }
                }
            ]
        }

    def test_successful_sql_response(self):
        """Response starting with SELECT is parsed as SQL."""
        service = self._create_service()
        mock_response = httpx.Response(
            status_code=200,
            json=self._make_chat_response("SELECT * FROM dataset"),
        )

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = service.generate("What is the total?")

        assert isinstance(result, LLMResponse)
        assert result.response_type == "sql"
        assert result.sql == "SELECT * FROM dataset"
        assert result.answer is None

    def test_successful_sql_response_with_markdown_code_block(self):
        """SQL wrapped in ```sql ... ``` is extracted correctly."""
        service = self._create_service()
        mock_response = httpx.Response(
            status_code=200,
            json=self._make_chat_response("```sql\nSELECT COUNT(*) FROM dataset\n```"),
        )

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = service.generate("How many rows?")

        assert result.response_type == "sql"
        assert result.sql == "SELECT COUNT(*) FROM dataset"

    def test_successful_answer_response(self):
        """Response not starting with SELECT is parsed as answer."""
        service = self._create_service()
        mock_response = httpx.Response(
            status_code=200,
            json=self._make_chat_response("The total is 42."),
        )

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = service.generate("What is the total?")

        assert isinstance(result, LLMResponse)
        assert result.response_type == "answer"
        assert result.answer == "The total is 42."
        assert result.sql is None

    def test_timeout_raises_llm_timeout_error(self):
        """LLMTimeoutError raised on httpx timeout."""
        service = self._create_service()

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.TimeoutException("timed out")
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMTimeoutError):
                service.generate("test prompt")

    def test_connect_error_raises_llm_unavailable_error(self):
        """LLMUnavailableError raised on connection failure."""
        service = self._create_service()

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.ConnectError("connection refused")
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMUnavailableError):
                service.generate("test prompt")

    def test_non_2xx_raises_llm_unavailable_error(self):
        """LLMUnavailableError raised on non-2xx response status."""
        service = self._create_service()
        mock_response = httpx.Response(status_code=500, text="Internal Server Error")

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMUnavailableError, match="HTTP 500"):
                service.generate("test prompt")

    def test_invalid_json_raises_llm_parse_error(self):
        """LLMParseError raised when response is not valid JSON."""
        service = self._create_service()
        mock_response = httpx.Response(
            status_code=200,
            text="not json at all",
            headers={"content-type": "text/plain"},
        )

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMParseError):
                service.generate("test prompt")

    def test_empty_choices_raises_llm_parse_error(self):
        """LLMParseError raised when choices array is empty."""
        service = self._create_service()
        mock_response = httpx.Response(
            status_code=200,
            json={"choices": []},
        )

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMParseError):
                service.generate("test prompt")

    def test_empty_content_raises_llm_parse_error(self):
        """LLMParseError raised when message content is empty."""
        service = self._create_service()
        mock_response = httpx.Response(
            status_code=200,
            json=self._make_chat_response(""),
        )

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMParseError):
                service.generate("test prompt")

    def test_response_not_dict_raises_llm_parse_error(self):
        """LLMParseError raised when response JSON is not a dict."""
        service = self._create_service()
        mock_response = httpx.Response(
            status_code=200,
            json=["not", "a", "dict"],
        )

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMParseError):
                service.generate("test prompt")

    def test_sends_correct_payload_format(self):
        """Verify the request is sent in OpenAI chat completions format."""
        service = self._create_service()
        mock_response = httpx.Response(
            status_code=200,
            json=self._make_chat_response("SELECT 1"),
        )

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            service.generate("test prompt")

            # Verify the call was made with correct format
            call_kwargs = mock_client.post.call_args
            payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs.kwargs["json"]
            assert payload["model"] == "test-model"
            assert payload["messages"][0]["role"] == "user"
            assert payload["messages"][0]["content"] == "test prompt"
