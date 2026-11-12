"""ChartGenerator service for chart specification generation.

Generates Chart.js-compatible JSON specifications from query results.
"""

import numpy as np
import pandas as pd

from app.exceptions import AnalyticsValidationError
from app.models.analytics_schemas import (
    ChartDataset,
    ChartRequest,
    ChartSpec,
    ChartType,
)
from app.services.analytics_engine import AnalyticsEngine


class ChartGenerator:
    """Chart specification generator.

    Uses AnalyticsEngine to apply filters before generating
    chart data for bar, line, pie, scatter, and histogram chart types.
    """

    def __init__(self, analytics_engine: AnalyticsEngine):
        self.analytics_engine = analytics_engine

    def generate(self, df: pd.DataFrame, request: ChartRequest) -> ChartSpec:
        """Generate a chart specification.

        Args:
            df: The input DataFrame to generate a chart from.
            request: The ChartRequest containing chart configuration.

        Returns:
            A ChartSpec with chart_type, labels, datasets, x_axis_label, y_axis_label.

        Raises:
            AnalyticsValidationError: If columns don't exist, types are invalid,
                or chart_type is unsupported.
        """
        # Apply filters if provided
        if request.filters:
            df = self.analytics_engine.apply_filters(df, request.filters)

        # Validate x_column exists
        if request.x_column not in df.columns:
            raise AnalyticsValidationError(
                f"Column '{request.x_column}' does not exist in dataset"
            )

        # Validate y_column exists (if provided and not histogram)
        if request.chart_type != ChartType.HISTOGRAM:
            if request.y_column is not None and request.y_column not in df.columns:
                raise AnalyticsValidationError(
                    f"Column '{request.y_column}' does not exist in dataset"
                )

        # Validate y_column is numeric for bar, line, pie, scatter
        # If the column is stored as object/string, attempt numeric coercion
        if request.chart_type in (ChartType.BAR, ChartType.LINE, ChartType.PIE, ChartType.SCATTER):
            if request.y_column is not None and not pd.api.types.is_numeric_dtype(df[request.y_column]):
                # Attempt to coerce string column to numeric
                coerced = pd.to_numeric(df[request.y_column], errors="coerce")
                if coerced.isna().all() and len(df[request.y_column].dropna()) > 0:
                    raise AnalyticsValidationError(
                        f"Column '{request.y_column}' must be numeric for {request.chart_type.value} charts"
                    )
                # Replace the column in-place with the coerced numeric values
                df = df.copy()
                df[request.y_column] = coerced

        # Validate group_by column exists (if provided)
        if request.group_by is not None and request.group_by not in df.columns:
            raise AnalyticsValidationError(
                f"Column '{request.group_by}' does not exist in dataset"
            )

        # Route to chart-type specific method
        if request.chart_type == ChartType.BAR:
            return self._generate_bar_line(df, request)
        elif request.chart_type == ChartType.LINE:
            return self._generate_bar_line(df, request)
        elif request.chart_type == ChartType.PIE:
            return self._generate_pie(df, request)
        elif request.chart_type == ChartType.SCATTER:
            return self._generate_scatter(df, request)
        elif request.chart_type == ChartType.HISTOGRAM:
            return self._generate_histogram(df, request)
        else:
            raise AnalyticsValidationError(
                "Unsupported chart type. Valid types: bar, line, pie, scatter, histogram"
            )

    def _sanitize_data(self, data: list) -> list[float | int | None]:
        """Convert NaN/None values to None for JSON null serialization."""
        result = []
        for val in data:
            if val is None or (isinstance(val, float) and np.isnan(val)):
                result.append(None)
            elif pd.isna(val):
                result.append(None)
            else:
                result.append(val)
        return result

    def _generate_bar_line(self, df: pd.DataFrame, request: ChartRequest) -> ChartSpec:
        """Generate bar or line chart specification.

        Supports optional group_by for multi-series charts (up to 50 distinct values).
        """
        x_column = request.x_column
        y_column = request.y_column

        if request.group_by is None:
            # Single series: labels from x_column, data from y_column
            labels = df[x_column].astype(str).tolist()
            data = self._sanitize_data(df[y_column].tolist())
            datasets = [ChartDataset(label=y_column, data=data)]
        else:
            # Multi-series: one dataset per unique group_by value
            group_col = request.group_by
            distinct_values = df[group_col].dropna().unique()

            if len(distinct_values) > 50:
                raise AnalyticsValidationError(
                    "group_by column has more than 50 distinct values"
                )

            # Get unique x labels
            labels = df[x_column].astype(str).unique().tolist()

            datasets = []
            for group_val in distinct_values:
                group_df = df[df[group_col] == group_val]
                # For each x label, get the corresponding y value
                group_x_values = group_df[x_column].astype(str).tolist()
                data = []
                for label in labels:
                    matching = group_df[group_df[x_column].astype(str) == label][y_column]
                    if len(matching) > 0:
                        data.append(matching.iloc[0])
                    else:
                        data.append(None)
                data = self._sanitize_data(data)
                datasets.append(ChartDataset(label=str(group_val), data=data))

        return ChartSpec(
            chart_type=request.chart_type.value,
            labels=labels,
            datasets=datasets,
            x_axis_label=x_column,
            y_axis_label=y_column,
        )

    def _generate_pie(self, df: pd.DataFrame, request: ChartRequest) -> ChartSpec:
        """Generate pie chart specification.

        x_column as labels, y_column as slice values.
        """
        x_column = request.x_column
        y_column = request.y_column

        labels = df[x_column].astype(str).tolist()
        data = self._sanitize_data(df[y_column].tolist())
        datasets = [ChartDataset(label=y_column, data=data)]

        return ChartSpec(
            chart_type=request.chart_type.value,
            labels=labels,
            datasets=datasets,
            x_axis_label=x_column,
            y_axis_label=y_column,
        )

    def _generate_scatter(self, df: pd.DataFrame, request: ChartRequest) -> ChartSpec:
        """Generate scatter chart specification.

        x_column and y_column as data points.
        """
        x_column = request.x_column
        y_column = request.y_column

        labels = df[x_column].astype(str).tolist()
        data = self._sanitize_data(df[y_column].tolist())
        datasets = [ChartDataset(label=y_column, data=data)]

        return ChartSpec(
            chart_type=request.chart_type.value,
            labels=labels,
            datasets=datasets,
            x_axis_label=x_column,
            y_axis_label=y_column,
        )

    def _generate_histogram(self, df: pd.DataFrame, request: ChartRequest) -> ChartSpec:
        """Generate histogram chart specification.

        x_column only, compute frequency distribution with configurable bins.
        """
        x_column = request.x_column

        # Validate x_column is numeric for histogram
        if not pd.api.types.is_numeric_dtype(df[x_column]):
            # Attempt to coerce string column to numeric
            coerced = pd.to_numeric(df[x_column], errors="coerce")
            if coerced.isna().all() and len(df[x_column].dropna()) > 0:
                raise AnalyticsValidationError(
                    f"Column '{x_column}' must be numeric for histogram charts"
                )
            df = df.copy()
            df[x_column] = coerced

        # Get non-null numeric values
        values = df[x_column].dropna().values

        # Compute histogram using numpy
        counts, bin_edges = np.histogram(values, bins=request.bins)

        # Create bin edge labels in "min - max" format
        labels = []
        for i in range(len(counts)):
            labels.append(f"{bin_edges[i]:.1f} - {bin_edges[i + 1]:.1f}")

        # Convert counts to list
        data = [int(c) for c in counts]
        datasets = [ChartDataset(label=x_column, data=data)]

        return ChartSpec(
            chart_type=request.chart_type.value,
            labels=labels,
            datasets=datasets,
            x_axis_label=x_column,
            y_axis_label="frequency",
        )
