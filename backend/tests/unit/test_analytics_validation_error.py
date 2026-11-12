"""Unit tests for AnalyticsValidationError exception and its handler."""

from fastapi.testclient import TestClient

from app.exceptions import AnalyticsValidationError
from app.main import app

client = TestClient(app)


class TestAnalyticsValidationError:
    """Tests for the AnalyticsValidationError exception class."""

    def test_exception_stores_message(self):
        exc = AnalyticsValidationError("Column 'foo' does not exist in dataset")
        assert exc.message == "Column 'foo' does not exist in dataset"
        assert str(exc) == "Column 'foo' does not exist in dataset"

    def test_exception_inherits_from_exception(self):
        exc = AnalyticsValidationError("test error")
        assert isinstance(exc, Exception)


class TestAnalyticsValidationErrorHandler:
    """Tests for the global exception handler returning HTTP 400."""

    def test_handler_returns_400_with_detail(self):
        # Add a temporary route that raises AnalyticsValidationError
        @app.get("/test-analytics-error")
        async def raise_analytics_error():
            raise AnalyticsValidationError("Column 'price' is not numeric; cannot apply 'sum'")

        response = client.get("/test-analytics-error")
        assert response.status_code == 400
        assert response.json() == {"detail": "Column 'price' is not numeric; cannot apply 'sum'"}

    def test_handler_returns_custom_message(self):
        @app.get("/test-analytics-error-custom")
        async def raise_analytics_error_custom():
            raise AnalyticsValidationError("between operator requires [min, max] where min <= max")

        response = client.get("/test-analytics-error-custom")
        assert response.status_code == 400
        assert response.json() == {"detail": "between operator requires [min, max] where min <= max"}
