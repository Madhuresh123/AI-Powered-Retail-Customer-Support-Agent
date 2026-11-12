"""REST Importer service for fetching and normalizing external API data."""

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
import pandas as pd

from app.exceptions import (
    InvalidURLError,
    PayloadTooLargeError,
    UpstreamError,
    UnsupportedFormatError,
)


@dataclass
class ImportResult:
    """Result of a successful REST API import."""

    dataframe: pd.DataFrame
    source_url: str
    row_count: int


class RESTImporter:
    """Fetches data from external REST API endpoints and normalizes to tabular format."""

    TIMEOUT_SECONDS = 30
    MAX_PAYLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

    def validate_url(self, url: str) -> None:
        """
        Validate URL format and scheme.

        Raises:
            InvalidURLError: URL is empty, malformed, or not http(s).
        """
        if not url or not url.strip():
            raise InvalidURLError(url=url, reason="URL must not be empty")

        try:
            parsed = urlparse(url)
        except Exception:
            raise InvalidURLError(url=url, reason="Malformed URL")

        if not parsed.scheme:
            raise InvalidURLError(url=url, reason="URL must include a scheme (http or https)")

        if parsed.scheme.lower() not in ("http", "https"):
            raise InvalidURLError(
                url=url,
                reason=f"URL scheme must be http or https, got '{parsed.scheme}'",
            )

        if not parsed.netloc:
            raise InvalidURLError(url=url, reason="URL must include a host")

    async def import_from_url(self, url: str) -> ImportResult:
        """
        Fetch data from an external URL and normalize into a DataFrame.

        Raises:
            InvalidURLError: URL is malformed or not http(s).
            UpstreamError: Connection failure, timeout, or non-2xx response.
            PayloadTooLargeError: Response exceeds 50 MB.
            UnsupportedFormatError: Not a JSON array of flat objects.
        """
        self.validate_url(url)

        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS) as client:
                async with client.stream("GET", url) as response:
                    if response.status_code < 200 or response.status_code >= 300:
                        raise UpstreamError(
                            reason=f"Upstream returned HTTP {response.status_code}"
                        )

                    # Stream response and check size limit
                    chunks: list[bytes] = []
                    total_size = 0

                    async for chunk in response.aiter_bytes():
                        total_size += len(chunk)
                        if total_size > self.MAX_PAYLOAD_SIZE:
                            raise PayloadTooLargeError(
                                size_bytes=total_size,
                                max_bytes=self.MAX_PAYLOAD_SIZE,
                            )
                        chunks.append(chunk)

        except PayloadTooLargeError:
            raise
        except UpstreamError:
            raise
        except httpx.TimeoutException:
            raise UpstreamError(reason="Request timed out after 30 seconds")
        except httpx.ConnectError:
            raise UpstreamError(reason="Failed to connect to upstream service")
        except httpx.HTTPError as exc:
            raise UpstreamError(reason=f"HTTP error: {str(exc)}")
        except Exception as exc:
            if isinstance(exc, (InvalidURLError, UnsupportedFormatError)):
                raise
            raise UpstreamError(reason=f"Connection error: {str(exc)}")

        # Parse JSON and normalize
        content = b"".join(chunks)

        try:
            import json

            data = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            raise UnsupportedFormatError(
                reason="Response is not valid JSON"
            )

        df = self.normalize_json(data)

        return ImportResult(
            dataframe=df,
            source_url=url,
            row_count=len(df),
        )

    def normalize_json(self, data: Any) -> pd.DataFrame:
        """
        Convert JSON array of flat objects to DataFrame.

        Raises:
            UnsupportedFormatError: If the data is not a JSON array of flat objects.
        """
        # Must be a list/array
        if not isinstance(data, list):
            raise UnsupportedFormatError(
                reason="Expected a JSON array at the top level"
            )

        # Must not be empty
        if len(data) == 0:
            raise UnsupportedFormatError(
                reason="JSON array must not be empty"
            )

        # Each element must be a flat object (dict with no nested structures)
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                raise UnsupportedFormatError(
                    reason=f"Expected array of objects, but element at index {i} is not an object"
                )
            for key, value in item.items():
                if isinstance(value, (dict, list)):
                    raise UnsupportedFormatError(
                        reason=f"Nested objects/arrays are not supported (found in key '{key}' at index {i})"
                    )

        df = pd.DataFrame(data)
        return df
