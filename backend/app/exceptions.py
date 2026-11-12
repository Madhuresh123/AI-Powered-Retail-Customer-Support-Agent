"""Custom exception classes for the Data Insight API."""


class DatasetNotFoundError(Exception):
    """Raised when a requested dataset does not exist in the store."""

    def __init__(self, dataset_id: str) -> None:
        self.dataset_id = dataset_id
        super().__init__(f"Dataset not found: {dataset_id}")


class FileTooLargeError(Exception):
    """Raised when an uploaded file exceeds the maximum allowed size (50 MB)."""

    def __init__(self, size_bytes: int, max_bytes: int = 50 * 1024 * 1024) -> None:
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
        super().__init__(
            f"File size {size_bytes} bytes exceeds maximum allowed size of {max_bytes} bytes"
        )


class InvalidCSVError(Exception):
    """Raised when the uploaded file is not valid CSV per RFC 4180."""

    def __init__(self, reason: str = "Invalid CSV format") -> None:
        self.reason = reason
        super().__init__(reason)


class InvalidEncodingError(Exception):
    """Raised when the uploaded file is not valid UTF-8."""

    def __init__(self, reason: str = "File is not valid UTF-8 encoding") -> None:
        self.reason = reason
        super().__init__(reason)


class EmptyDataError(Exception):
    """Raised when a CSV file contains a header row but zero data rows."""

    def __init__(self) -> None:
        super().__init__("CSV file contains a header row but no data rows")


class TooManyColumnsError(Exception):
    """Raised when a CSV file contains more than 500 columns."""

    def __init__(self, column_count: int, max_columns: int = 500) -> None:
        self.column_count = column_count
        self.max_columns = max_columns
        super().__init__(
            f"CSV file has {column_count} columns, exceeding the maximum of {max_columns}"
        )


class InvalidURLError(Exception):
    """Raised when the provided URL is malformed or does not use http/https."""

    def __init__(self, url: str, reason: str = "Invalid URL") -> None:
        self.url = url
        self.reason = reason
        super().__init__(f"{reason}: {url}")


class UpstreamError(Exception):
    """Raised when the external API is unreachable, times out, or returns non-2xx."""

    def __init__(self, reason: str = "Upstream service error") -> None:
        self.reason = reason
        super().__init__(reason)


class PayloadTooLargeError(Exception):
    """Raised when the response payload from an external URL exceeds 50 MB."""

    def __init__(self, size_bytes: int, max_bytes: int = 50 * 1024 * 1024) -> None:
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
        super().__init__(
            f"Response payload {size_bytes} bytes exceeds maximum of {max_bytes} bytes"
        )


class UnsupportedFormatError(Exception):
    """Raised when the response is not a JSON array of flat objects."""

    def __init__(self, reason: str = "Unsupported format: expected a JSON array of flat objects") -> None:
        self.reason = reason
        super().__init__(reason)


class AnalyticsValidationError(Exception):
    """Raised for 400-level business logic errors in the Analytics Engine.

    Used for invalid column references, type mismatches, invalid operator usage,
    and other query validation failures.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class QueryValidationError(Exception):
    """Raised when a SQL query fails safety validation."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class QueryExecutionError(Exception):
    """Raised when SQL execution fails or times out."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class LLMUnavailableError(Exception):
    """Raised when LLM provider is unreachable or returns non-2xx."""

    def __init__(self, message: str = "AI service is temporarily unavailable") -> None:
        self.message = message
        super().__init__(message)


class LLMTimeoutError(Exception):
    """Raised when LLM provider does not respond within timeout."""

    def __init__(self, message: str = "AI service request timed out") -> None:
        self.message = message
        super().__init__(message)


class LLMParseError(Exception):
    """Raised when LLM response cannot be parsed."""

    def __init__(self, message: str = "AI service returned an invalid response") -> None:
        self.message = message
        super().__init__(message)


class ConfigurationError(Exception):
    """Raised when required configuration is missing."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)
