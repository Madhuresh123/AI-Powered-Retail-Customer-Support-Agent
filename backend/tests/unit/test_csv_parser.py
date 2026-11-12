"""Unit tests for the CSVParser service."""

import io
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from app.exceptions import (
    EmptyDataError,
    FileTooLargeError,
    InvalidCSVError,
    InvalidEncodingError,
    TooManyColumnsError,
)
from app.services.csv_parser import CSVParser, ParseResult


def _make_upload_file(content: bytes, filename: str = "test.csv") -> MagicMock:
    """Create a mock UploadFile with given content."""
    mock_file = MagicMock()
    mock_file.filename = filename
    buffer = io.BytesIO(content)

    async def mock_read(size: int = -1) -> bytes:
        return buffer.read(size)

    mock_file.read = mock_read
    return mock_file


@pytest.fixture
def parser():
    return CSVParser()


class TestValidateEncoding:
    """Tests for validate_encoding method."""

    def test_valid_utf8(self, parser):
        content = "hello,world\n1,2".encode("utf-8")
        result = parser.validate_encoding(content)
        assert result == "hello,world\n1,2"

    def test_valid_utf8_with_special_chars(self, parser):
        content = "name,city\nJosé,München".encode("utf-8")
        result = parser.validate_encoding(content)
        assert "José" in result
        assert "München" in result

    def test_invalid_utf8_raises_error(self, parser):
        content = b"\xff\xfe\x00\x01"
        with pytest.raises(InvalidEncodingError):
            parser.validate_encoding(content)

    def test_invalid_utf8_continuation_bytes(self, parser):
        content = b"hello\x80world"
        with pytest.raises(InvalidEncodingError):
            parser.validate_encoding(content)


class TestValidateStructure:
    """Tests for validate_structure method."""

    def test_valid_structure(self, parser):
        df = pd.DataFrame({"a": ["1"], "b": ["2"]})
        # Should not raise
        parser.validate_structure(df, list(df.columns))

    def test_empty_dataframe_raises_error(self, parser):
        df = pd.DataFrame(columns=["a", "b"])
        with pytest.raises(EmptyDataError):
            parser.validate_structure(df, list(df.columns))

    def test_too_many_columns_raises_error(self, parser):
        cols = [f"col_{i}" for i in range(501)]
        df = pd.DataFrame([["x"] * 501], columns=cols)
        with pytest.raises(TooManyColumnsError) as exc_info:
            parser.validate_structure(df, cols)
        assert exc_info.value.column_count == 501
        assert exc_info.value.max_columns == 500

    def test_exactly_500_columns_is_valid(self, parser):
        cols = [f"col_{i}" for i in range(500)]
        df = pd.DataFrame([["x"] * 500], columns=cols)
        # Should not raise
        parser.validate_structure(df, cols)


class TestParseCSV:
    """Tests for the _parse_csv internal method."""

    def test_simple_csv(self, parser):
        content = "name,age\nAlice,30\nBob,25"
        df = parser._parse_csv(content)
        assert list(df.columns) == ["name", "age"]
        assert len(df) == 2
        assert df.iloc[0]["name"] == "Alice"
        assert df.iloc[0]["age"] == "30"

    def test_quoted_fields(self, parser):
        content = 'name,description\nAlice,"She said ""hello"""\nBob,"A, B, C"'
        df = parser._parse_csv(content)
        assert df.iloc[0]["description"] == 'She said "hello"'
        assert df.iloc[1]["description"] == "A, B, C"

    def test_multiline_values(self, parser):
        content = 'name,address\nAlice,"123 Main St\nApt 4"\nBob,"456 Oak Ave"'
        df = parser._parse_csv(content)
        assert "123 Main St\nApt 4" == df.iloc[0]["address"]
        assert len(df) == 2

    def test_empty_cells_preserved_as_empty_strings(self, parser):
        content = "a,b,c\n1,,3\n,,\n4,5,"
        df = parser._parse_csv(content)
        assert df.iloc[0]["b"] == ""
        assert df.iloc[1]["a"] == ""
        assert df.iloc[1]["b"] == ""
        assert df.iloc[1]["c"] == ""
        assert df.iloc[2]["c"] == ""

    def test_column_ordering_preserved(self, parser):
        content = "zebra,apple,mango\n1,2,3"
        df = parser._parse_csv(content)
        assert list(df.columns) == ["zebra", "apple", "mango"]

    def test_empty_content_raises_error(self, parser):
        with pytest.raises(InvalidCSVError):
            parser._parse_csv("")

    def test_whitespace_only_raises_error(self, parser):
        with pytest.raises(InvalidCSVError):
            parser._parse_csv("   \n  \n  ")

    def test_escaped_commas_in_fields(self, parser):
        content = 'city,population\n"New York, NY","8,336,817"'
        df = parser._parse_csv(content)
        assert df.iloc[0]["city"] == "New York, NY"
        assert df.iloc[0]["population"] == "8,336,817"


class TestParse:
    """Integration tests for the full parse method."""

    @pytest.mark.asyncio
    async def test_parse_valid_csv(self, parser):
        content = b"name,age\nAlice,30\nBob,25"
        file = _make_upload_file(content, "people.csv")
        result = await parser.parse(file)

        assert isinstance(result, ParseResult)
        assert result.filename == "people.csv"
        assert result.row_count == 2
        assert result.column_count == 2
        assert list(result.dataframe.columns) == ["name", "age"]

    @pytest.mark.asyncio
    async def test_parse_invalid_encoding(self, parser):
        content = b"\xff\xfe\x00\x01col1,col2\n"
        file = _make_upload_file(content)
        with pytest.raises(InvalidEncodingError):
            await parser.parse(file)

    @pytest.mark.asyncio
    async def test_parse_empty_data_rows(self, parser):
        content = b"col1,col2\n"
        file = _make_upload_file(content)
        with pytest.raises(EmptyDataError):
            await parser.parse(file)

    @pytest.mark.asyncio
    async def test_parse_too_many_columns(self, parser):
        cols = ",".join([f"col_{i}" for i in range(501)])
        row = ",".join(["x"] * 501)
        content = f"{cols}\n{row}".encode("utf-8")
        file = _make_upload_file(content)
        with pytest.raises(TooManyColumnsError):
            await parser.parse(file)

    @pytest.mark.asyncio
    async def test_parse_file_too_large(self, parser):
        # Create content that exceeds 50MB
        parser.MAX_FILE_SIZE = 100  # Override for testing
        content = b"a,b\n" + b"x,y\n" * 50
        file = _make_upload_file(content)
        with pytest.raises(FileTooLargeError):
            await parser.parse(file)

    @pytest.mark.asyncio
    async def test_parse_preserves_empty_cells(self, parser):
        content = b"a,b,c\n1,,3\n,,\n"
        file = _make_upload_file(content)
        result = await parser.parse(file)

        assert result.dataframe.iloc[0]["b"] == ""
        assert result.dataframe.iloc[1]["a"] == ""
        assert result.dataframe.iloc[1]["b"] == ""
        assert result.dataframe.iloc[1]["c"] == ""

    @pytest.mark.asyncio
    async def test_parse_no_filename_defaults(self, parser):
        content = b"a,b\n1,2\n"
        mock_file = MagicMock()
        mock_file.filename = None
        buffer = io.BytesIO(content)

        async def mock_read(size: int = -1) -> bytes:
            return buffer.read(size)

        mock_file.read = mock_read
        result = await parser.parse(mock_file)
        assert result.filename == "unnamed.csv"
