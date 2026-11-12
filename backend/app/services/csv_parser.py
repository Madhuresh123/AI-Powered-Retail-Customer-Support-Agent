"""CSV Parser service for parsing and validating uploaded CSV files."""

import io
from dataclasses import dataclass

import pandas as pd
from fastapi import UploadFile

from app.exceptions import (
    EmptyDataError,
    FileTooLargeError,
    InvalidCSVError,
    InvalidEncodingError,
    TooManyColumnsError,
)


@dataclass
class ParseResult:
    """Result of parsing a CSV file."""

    dataframe: pd.DataFrame
    filename: str
    row_count: int
    column_count: int


class CSVParser:
    """Responsible for parsing and validating uploaded CSV files.

    Validates UTF-8 encoding, enforces size limits, parses CSV content
    according to RFC 4180 rules, and validates structural constraints.
    """

    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
    MAX_COLUMNS = 500

    async def parse(self, file: UploadFile) -> ParseResult:
        """Parse a CSV file into a DataFrame.

        Reads the file content, validates encoding and size, parses
        the CSV using RFC 4180 rules, and validates structure.

        Args:
            file: The uploaded file from the multipart form request.

        Returns:
            ParseResult with the parsed DataFrame and metadata.

        Raises:
            FileTooLargeError: File exceeds 50 MB.
            InvalidEncodingError: File is not valid UTF-8.
            InvalidCSVError: File is not valid CSV per RFC 4180.
            EmptyDataError: Header present but no data rows.
            TooManyColumnsError: More than 500 columns.
        """
        # Read file content with streaming size check
        content = await self._read_with_size_check(file)

        # Validate UTF-8 encoding
        decoded_content = self.validate_encoding(content)

        # Parse CSV content
        df = self._parse_csv(decoded_content)

        # Validate structure (row count, column count)
        header = list(df.columns)
        self.validate_structure(df, header)

        filename = file.filename or "unnamed.csv"

        return ParseResult(
            dataframe=df,
            filename=filename,
            row_count=len(df),
            column_count=len(df.columns),
        )

    async def _read_with_size_check(self, file: UploadFile) -> bytes:
        """Read the uploaded file content while checking size limit.

        Streams the file in chunks to fail fast if size exceeds limit.

        Args:
            file: The uploaded file.

        Returns:
            The full file content as bytes.

        Raises:
            FileTooLargeError: If file size exceeds MAX_FILE_SIZE.
        """
        chunks: list[bytes] = []
        total_size = 0
        chunk_size = 64 * 1024  # 64 KB chunks

        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > self.MAX_FILE_SIZE:
                raise FileTooLargeError(
                    size_bytes=total_size, max_bytes=self.MAX_FILE_SIZE
                )
            chunks.append(chunk)

        return b"".join(chunks)

    def validate_encoding(self, content: bytes) -> str:
        """Validate that the content is valid UTF-8 encoding.

        Args:
            content: Raw bytes from the uploaded file.

        Returns:
            The decoded string content.

        Raises:
            InvalidEncodingError: If the content is not valid UTF-8.
        """
        try:
            return content.decode("utf-8")
        except (UnicodeDecodeError, ValueError) as e:
            raise InvalidEncodingError(
                reason=f"File is not valid UTF-8 encoding: {e}"
            )

    def validate_structure(self, df: pd.DataFrame, header: list[str]) -> None:
        """Validate row count and column count constraints.

        Args:
            df: The parsed DataFrame.
            header: The list of column headers.

        Raises:
            EmptyDataError: If there are zero data rows.
            TooManyColumnsError: If there are more than MAX_COLUMNS columns.
        """
        if len(df) == 0:
            raise EmptyDataError()

        column_count = len(header)
        if column_count > self.MAX_COLUMNS:
            raise TooManyColumnsError(
                column_count=column_count, max_columns=self.MAX_COLUMNS
            )

    def _parse_csv(self, content: str) -> pd.DataFrame:
        """Parse CSV content into a DataFrame using RFC 4180 rules.

        Handles quoted fields, escaped commas, escaped double-quotes,
        and multi-line cell values. Preserves empty cells as empty strings
        and maintains column ordering from the original header row.

        Args:
            content: The decoded CSV string content.

        Returns:
            A pandas DataFrame with the parsed data.

        Raises:
            InvalidCSVError: If the content cannot be parsed as valid CSV.
        """
        if not content.strip():
            raise InvalidCSVError(reason="File is empty")

        try:
            df = pd.read_csv(
                io.StringIO(content),
                # RFC 4180: double-quote is the quoting character
                quotechar='"',
                # RFC 4180: use double-quote to escape quotes within fields
                doublequote=True,
                # Keep all values as strings to preserve fidelity
                dtype=str,
                # Do not interpret any values as NA/NaN
                keep_default_na=False,
                na_values=[],
                # Use the Python engine for better RFC 4180 compliance
                # (handles multi-line quoted fields)
                engine="python",
                # Do not skip initial whitespace
                skipinitialspace=False,
                # Standard comma separator
                sep=",",
            )
        except pd.errors.EmptyDataError:
            raise InvalidCSVError(reason="File contains no parseable CSV data")
        except pd.errors.ParserError as e:
            raise InvalidCSVError(reason=f"CSV parsing error: {e}")
        except Exception as e:
            raise InvalidCSVError(reason=f"Failed to parse CSV: {e}")

        # Ensure empty cells are preserved as empty strings, not NaN
        df = df.fillna("")

        return df
