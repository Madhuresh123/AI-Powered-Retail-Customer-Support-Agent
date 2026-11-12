"""Unit tests for the RESTImporter class."""

import json
from unittest.mock import patch

import httpx
import pandas as pd
import pytest

from app.exceptions import (
    InvalidURLError,
    PayloadTooLargeError,
    UpstreamError,
    UnsupportedFormatError,
)
from app.services.rest_importer import ImportResult, RESTImporter


@pytest.fixture
def importer():
    return RESTImporter()


class TestValidateUrl:
    """Tests for validate_url method."""

    def test_valid_http_url(self, importer):
        """Valid http URL should not raise."""
        importer.validate_url("http://example.com/data.json")

    def test_valid_https_url(self, importer):
        """Valid https URL should not raise."""
        importer.validate_url("https://api.example.com/v1/records")

    def test_empty_url_raises(self, importer):
        """Empty string raises InvalidURLError."""
        with pytest.raises(InvalidURLError):
            importer.validate_url("")

    def test_whitespace_url_raises(self, importer):
        """Whitespace-only string raises InvalidURLError."""
        with pytest.raises(InvalidURLError):
            importer.validate_url("   ")

    def test_ftp_scheme_raises(self, importer):
        """FTP scheme raises InvalidURLError."""
        with pytest.raises(InvalidURLError):
            importer.validate_url("ftp://example.com/data")

    def test_no_scheme_raises(self, importer):
        """URL without scheme raises InvalidURLError."""
        with pytest.raises(InvalidURLError):
            importer.validate_url("example.com/data")

    def test_no_host_raises(self, importer):
        """URL without host raises InvalidURLError."""
        with pytest.raises(InvalidURLError):
            importer.validate_url("http://")

    def test_random_text_raises(self, importer):
        """Random text raises InvalidURLError."""
        with pytest.raises(InvalidURLError):
            importer.validate_url("not-a-url")


class TestNormalizeJson:
    """Tests for normalize_json method."""

    def test_valid_array_of_flat_objects(self, importer):
        """Array of flat objects returns DataFrame."""
        data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ]
        df = importer.normalize_json(data)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert list(df.columns) == ["name", "age"]

    def test_non_array_raises(self, importer):
        """Non-array JSON raises UnsupportedFormatError."""
        with pytest.raises(UnsupportedFormatError):
            importer.normalize_json({"key": "value"})

    def test_empty_array_raises(self, importer):
        """Empty array raises UnsupportedFormatError."""
        with pytest.raises(UnsupportedFormatError):
            importer.normalize_json([])

    def test_array_of_primitives_raises(self, importer):
        """Array of primitives raises UnsupportedFormatError."""
        with pytest.raises(UnsupportedFormatError):
            importer.normalize_json([1, 2, 3])

    def test_nested_objects_raises(self, importer):
        """Objects with nested dicts raise UnsupportedFormatError."""
        data = [{"name": "Alice", "address": {"city": "NYC"}}]
        with pytest.raises(UnsupportedFormatError):
            importer.normalize_json(data)

    def test_nested_arrays_raises(self, importer):
        """Objects with nested arrays raise UnsupportedFormatError."""
        data = [{"name": "Alice", "tags": ["a", "b"]}]
        with pytest.raises(UnsupportedFormatError):
            importer.normalize_json(data)

    def test_mixed_types_in_values_allowed(self, importer):
        """Flat objects with None, int, str, float, bool values are allowed."""
        data = [
            {"name": "Alice", "age": 30, "active": True, "score": 9.5, "note": None},
        ]
        df = importer.normalize_json(data)
        assert len(df) == 1


class _AsyncByteStream:
    """Helper async iterator for mocking aiter_bytes()."""

    def __init__(self, chunks: list[bytes]):
        self._chunks = chunks
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk


class _MockStreamResponse:
    """Context manager mock for httpx streaming response."""

    def __init__(self, status_code: int, chunks: list[bytes]):
        self.status_code = status_code
        self._chunks = chunks

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def aiter_bytes(self):
        return _AsyncByteStream(self._chunks)


class _ErrorStreamContext:
    """Context manager that raises on enter (simulates stream() raising)."""

    def __init__(self, error: Exception):
        self._error = error

    async def __aenter__(self):
        raise self._error

    async def __aexit__(self, *args):
        pass


class _MockAsyncClient:
    """Context manager mock for httpx.AsyncClient."""

    def __init__(self, response: _MockStreamResponse = None, error: Exception = None):
        self._response = response
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def stream(self, method: str, url: str):
        if self._error:
            return _ErrorStreamContext(self._error)
        return self._response


class TestImportFromUrl:
    """Tests for import_from_url method."""

    @pytest.mark.asyncio
    async def test_successful_import(self, importer):
        """Successful import returns ImportResult with correct data."""
        json_data = [{"id": 1, "value": "a"}, {"id": 2, "value": "b"}]
        content = json.dumps(json_data).encode()

        mock_response = _MockStreamResponse(status_code=200, chunks=[content])
        mock_client = _MockAsyncClient(response=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await importer.import_from_url("https://api.example.com/data")

        assert isinstance(result, ImportResult)
        assert result.source_url == "https://api.example.com/data"
        assert result.row_count == 2
        assert len(result.dataframe) == 2

    @pytest.mark.asyncio
    async def test_invalid_url_raises(self, importer):
        """Invalid URL raises InvalidURLError before any HTTP call."""
        with pytest.raises(InvalidURLError):
            await importer.import_from_url("ftp://bad.com/data")

    @pytest.mark.asyncio
    async def test_timeout_raises_upstream_error(self, importer):
        """Timeout raises UpstreamError."""
        mock_client = _MockAsyncClient(error=httpx.TimeoutException("timeout"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(UpstreamError):
                await importer.import_from_url("https://slow.example.com/data")

    @pytest.mark.asyncio
    async def test_connect_error_raises_upstream_error(self, importer):
        """Connection error raises UpstreamError."""
        mock_client = _MockAsyncClient(error=httpx.ConnectError("refused"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(UpstreamError):
                await importer.import_from_url("https://down.example.com/data")

    @pytest.mark.asyncio
    async def test_non_2xx_raises_upstream_error(self, importer):
        """Non-2xx response raises UpstreamError."""
        mock_response = _MockStreamResponse(status_code=500, chunks=[])
        mock_client = _MockAsyncClient(response=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(UpstreamError):
                await importer.import_from_url("https://api.example.com/fail")

    @pytest.mark.asyncio
    async def test_invalid_json_raises_unsupported_format(self, importer):
        """Invalid JSON body raises UnsupportedFormatError."""
        content = b"not json at all"

        mock_response = _MockStreamResponse(status_code=200, chunks=[content])
        mock_client = _MockAsyncClient(response=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(UnsupportedFormatError):
                await importer.import_from_url("https://api.example.com/text")
