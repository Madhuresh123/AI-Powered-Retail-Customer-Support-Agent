"""Analytics Engine request and response schemas."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- Enums ---


class FilterOperator(str, Enum):
    """Supported filter comparison operators."""

    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    BETWEEN = "between"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IN = "in"


class AggregationFunction(str, Enum):
    """Supported aggregation functions."""

    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    MEDIAN = "median"
    STD = "std"
    DISTINCT_COUNT = "distinct_count"


class SortDirection(str, Enum):
    """Sort direction options."""

    ASC = "asc"
    DESC = "desc"


class ChartType(str, Enum):
    """Supported chart types."""

    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"


# --- Request Models ---


class FilterExpression(BaseModel):
    """A single filter condition applied to a column."""

    column: str
    operator: FilterOperator
    value: Any  # scalar, list, or two-element array for between


class AggregationOp(BaseModel):
    """A single aggregation operation to apply."""

    function: AggregationFunction
    column: str


class SortSpec(BaseModel):
    """Sort specification for a single column."""

    column: str
    direction: SortDirection = SortDirection.ASC


class QueryRequest(BaseModel):
    """Combined query request with filters, search, aggregations, sort, and pagination."""

    filters: list[FilterExpression] | None = None
    search: str | None = None
    search_columns: list[str] | None = None
    aggregations: list[AggregationOp] | None = None
    group_by: list[str] | None = Field(None, max_length=5)
    sort: list[SortSpec] | None = Field(None, max_length=10)
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=1000)


class ChartRequest(BaseModel):
    """Request to generate a chart specification."""

    chart_type: ChartType
    x_column: str
    y_column: str | None = None  # Optional for histogram
    group_by: str | None = None
    filters: list[FilterExpression] | None = None
    bins: int = Field(10, ge=1, le=1000)


class SQLRequest(BaseModel):
    """Request to execute a SQL query against a dataset."""

    query: str = Field(..., min_length=1, max_length=4096)


# --- Response Models ---


class PaginationMeta(BaseModel):
    """Pagination metadata included in query responses."""

    total_rows: int
    total_pages: int
    current_page: int
    page_size: int


class QueryResponse(BaseModel):
    """Response from the query endpoint."""

    columns: list[str]
    rows: list[dict[str, Any]]
    pagination: PaginationMeta


class ChartDataset(BaseModel):
    """A single data series in a chart specification."""

    label: str
    data: list[float | int | None]


class ChartSpec(BaseModel):
    """Chart.js-compatible chart specification."""

    chart_type: str
    labels: list[str]
    datasets: list[ChartDataset]
    x_axis_label: str
    y_axis_label: str


class SQLResponse(BaseModel):
    """Response from the SQL query endpoint."""

    columns: list[str]
    rows: list[dict[str, Any]]
