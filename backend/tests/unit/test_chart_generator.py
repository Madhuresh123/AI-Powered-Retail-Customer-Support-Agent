"""Unit tests for ChartGenerator service."""

import numpy as np
import pandas as pd
import pytest

from app.exceptions import AnalyticsValidationError
from app.models.analytics_schemas import (
    ChartDataset,
    ChartRequest,
    ChartSpec,
    ChartType,
    FilterExpression,
    FilterOperator,
)
from app.services.analytics_engine import AnalyticsEngine
from app.services.chart_generator import ChartGenerator


@pytest.fixture
def analytics_engine():
    return AnalyticsEngine()


@pytest.fixture
def chart_generator(analytics_engine):
    return ChartGenerator(analytics_engine)


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "category": ["A", "B", "C", "D", "E"],
        "value": [10, 20, 30, 40, 50],
        "group": ["X", "X", "Y", "Y", "X"],
        "score": [1.5, 2.5, 3.5, 4.5, 5.5],
    })


@pytest.fixture
def numeric_df():
    return pd.DataFrame({
        "x": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
        "y": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
    })


class TestBarChart:
    def test_basic_bar_chart(self, chart_generator, sample_df):
        request = ChartRequest(
            chart_type=ChartType.BAR,
            x_column="category",
            y_column="value",
        )
        result = chart_generator.generate(sample_df, request)

        assert result.chart_type == "bar"
        assert result.labels == ["A", "B", "C", "D", "E"]
        assert len(result.datasets) == 1
        assert result.datasets[0].label == "value"
        assert result.datasets[0].data == [10, 20, 30, 40, 50]
        assert result.x_axis_label == "category"
        assert result.y_axis_label == "value"

    def test_bar_chart_with_group_by(self, chart_generator, sample_df):
        request = ChartRequest(
            chart_type=ChartType.BAR,
            x_column="category",
            y_column="value",
            group_by="group",
        )
        result = chart_generator.generate(sample_df, request)

        assert result.chart_type == "bar"
        assert len(result.datasets) == 2  # X and Y groups
        # Each dataset label should be a group value
        dataset_labels = {ds.label for ds in result.datasets}
        assert dataset_labels == {"X", "Y"}

    def test_bar_chart_group_by_exceeds_50(self, chart_generator):
        # Create a DataFrame with more than 50 distinct group values
        df = pd.DataFrame({
            "category": list(range(60)),
            "value": list(range(60)),
            "group": [f"g{i}" for i in range(60)],
        })
        request = ChartRequest(
            chart_type=ChartType.BAR,
            x_column="category",
            y_column="value",
            group_by="group",
        )
        with pytest.raises(AnalyticsValidationError, match="group_by column has more than 50 distinct values"):
            chart_generator.generate(df, request)


class TestLineChart:
    def test_basic_line_chart(self, chart_generator, sample_df):
        request = ChartRequest(
            chart_type=ChartType.LINE,
            x_column="category",
            y_column="value",
        )
        result = chart_generator.generate(sample_df, request)

        assert result.chart_type == "line"
        assert result.labels == ["A", "B", "C", "D", "E"]
        assert len(result.datasets) == 1
        assert result.datasets[0].label == "value"
        assert result.datasets[0].data == [10, 20, 30, 40, 50]

    def test_line_chart_with_group_by(self, chart_generator, sample_df):
        request = ChartRequest(
            chart_type=ChartType.LINE,
            x_column="category",
            y_column="value",
            group_by="group",
        )
        result = chart_generator.generate(sample_df, request)

        assert result.chart_type == "line"
        assert len(result.datasets) == 2


class TestPieChart:
    def test_basic_pie_chart(self, chart_generator, sample_df):
        request = ChartRequest(
            chart_type=ChartType.PIE,
            x_column="category",
            y_column="value",
        )
        result = chart_generator.generate(sample_df, request)

        assert result.chart_type == "pie"
        assert result.labels == ["A", "B", "C", "D", "E"]
        assert len(result.datasets) == 1
        assert result.datasets[0].label == "value"
        assert result.datasets[0].data == [10, 20, 30, 40, 50]
        assert result.x_axis_label == "category"
        assert result.y_axis_label == "value"


class TestScatterChart:
    def test_basic_scatter_chart(self, chart_generator, numeric_df):
        request = ChartRequest(
            chart_type=ChartType.SCATTER,
            x_column="x",
            y_column="y",
        )
        result = chart_generator.generate(numeric_df, request)

        assert result.chart_type == "scatter"
        assert result.labels == ["1.0", "2.0", "3.0", "4.0", "5.0", "6.0", "7.0", "8.0", "9.0", "10.0"]
        assert len(result.datasets) == 1
        assert result.datasets[0].data == [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        assert result.x_axis_label == "x"
        assert result.y_axis_label == "y"


class TestHistogramChart:
    def test_basic_histogram(self, chart_generator, numeric_df):
        request = ChartRequest(
            chart_type=ChartType.HISTOGRAM,
            x_column="x",
            bins=5,
        )
        result = chart_generator.generate(numeric_df, request)

        assert result.chart_type == "histogram"
        assert len(result.labels) == 5
        assert len(result.datasets) == 1
        assert result.y_axis_label == "frequency"
        assert result.x_axis_label == "x"
        # Sum of frequencies should equal number of non-null rows
        assert sum(result.datasets[0].data) == 10

    def test_histogram_default_bins(self, chart_generator, numeric_df):
        request = ChartRequest(
            chart_type=ChartType.HISTOGRAM,
            x_column="x",
        )
        result = chart_generator.generate(numeric_df, request)

        # Default bins is 10
        assert len(result.labels) == 10
        assert sum(result.datasets[0].data) == 10

    def test_histogram_non_numeric_column(self, chart_generator, sample_df):
        request = ChartRequest(
            chart_type=ChartType.HISTOGRAM,
            x_column="category",
        )
        with pytest.raises(AnalyticsValidationError, match="must be numeric for histogram"):
            chart_generator.generate(sample_df, request)

    def test_histogram_with_nan_values(self, chart_generator):
        df = pd.DataFrame({"x": [1.0, 2.0, np.nan, 4.0, 5.0, np.nan]})
        request = ChartRequest(
            chart_type=ChartType.HISTOGRAM,
            x_column="x",
            bins=4,
        )
        result = chart_generator.generate(df, request)

        # Only 4 non-null values
        assert sum(result.datasets[0].data) == 4

    def test_histogram_label_format(self, chart_generator, numeric_df):
        request = ChartRequest(
            chart_type=ChartType.HISTOGRAM,
            x_column="x",
            bins=2,
        )
        result = chart_generator.generate(numeric_df, request)

        # Labels should be in "min - max" format
        for label in result.labels:
            parts = label.split(" - ")
            assert len(parts) == 2
            float(parts[0])  # Should be parseable as float
            float(parts[1])


class TestValidation:
    def test_invalid_x_column(self, chart_generator, sample_df):
        request = ChartRequest(
            chart_type=ChartType.BAR,
            x_column="nonexistent",
            y_column="value",
        )
        with pytest.raises(AnalyticsValidationError, match="does not exist in dataset"):
            chart_generator.generate(sample_df, request)

    def test_invalid_y_column(self, chart_generator, sample_df):
        request = ChartRequest(
            chart_type=ChartType.BAR,
            x_column="category",
            y_column="nonexistent",
        )
        with pytest.raises(AnalyticsValidationError, match="does not exist in dataset"):
            chart_generator.generate(sample_df, request)

    def test_non_numeric_y_column_bar(self, chart_generator, sample_df):
        request = ChartRequest(
            chart_type=ChartType.BAR,
            x_column="value",
            y_column="category",
        )
        with pytest.raises(AnalyticsValidationError, match="must be numeric for bar charts"):
            chart_generator.generate(sample_df, request)

    def test_non_numeric_y_column_line(self, chart_generator, sample_df):
        request = ChartRequest(
            chart_type=ChartType.LINE,
            x_column="value",
            y_column="category",
        )
        with pytest.raises(AnalyticsValidationError, match="must be numeric for line charts"):
            chart_generator.generate(sample_df, request)

    def test_non_numeric_y_column_pie(self, chart_generator, sample_df):
        request = ChartRequest(
            chart_type=ChartType.PIE,
            x_column="value",
            y_column="category",
        )
        with pytest.raises(AnalyticsValidationError, match="must be numeric for pie charts"):
            chart_generator.generate(sample_df, request)

    def test_non_numeric_y_column_scatter(self, chart_generator, sample_df):
        request = ChartRequest(
            chart_type=ChartType.SCATTER,
            x_column="value",
            y_column="category",
        )
        with pytest.raises(AnalyticsValidationError, match="must be numeric for scatter charts"):
            chart_generator.generate(sample_df, request)

    def test_invalid_group_by_column(self, chart_generator, sample_df):
        request = ChartRequest(
            chart_type=ChartType.BAR,
            x_column="category",
            y_column="value",
            group_by="nonexistent",
        )
        with pytest.raises(AnalyticsValidationError, match="does not exist in dataset"):
            chart_generator.generate(sample_df, request)


class TestFilters:
    def test_filters_applied_before_chart(self, chart_generator, sample_df):
        request = ChartRequest(
            chart_type=ChartType.BAR,
            x_column="category",
            y_column="value",
            filters=[
                FilterExpression(column="value", operator=FilterOperator.GT, value=20)
            ],
        )
        result = chart_generator.generate(sample_df, request)

        # Only rows with value > 20 should be included (C=30, D=40, E=50)
        assert result.labels == ["C", "D", "E"]
        assert result.datasets[0].data == [30, 40, 50]


class TestNullHandling:
    def test_nan_in_y_values(self, chart_generator):
        df = pd.DataFrame({
            "category": ["A", "B", "C"],
            "value": [10.0, np.nan, 30.0],
        })
        request = ChartRequest(
            chart_type=ChartType.BAR,
            x_column="category",
            y_column="value",
        )
        result = chart_generator.generate(df, request)

        assert result.datasets[0].data == [10.0, None, 30.0]
