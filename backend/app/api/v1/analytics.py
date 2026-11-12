"""API v1 analytics endpoints for query, SQL, and chart generation."""

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_analytics_engine, get_chart_generator, get_dataset_service, get_sql_engine
from app.exceptions import DatasetNotFoundError
from app.models.analytics_schemas import (
    ChartRequest,
    ChartSpec,
    QueryRequest,
    QueryResponse,
    SQLRequest,
    SQLResponse,
)
from app.services.analytics_engine import AnalyticsEngine
from app.services.chart_generator import ChartGenerator
from app.services.dataset_service import DatasetService
from app.services.sql_engine import SQLEngine

router = APIRouter(prefix="/datasets", tags=["analytics"])


@router.post("/{dataset_id}/query", response_model=QueryResponse)
async def query_dataset(
    dataset_id: str,
    request: QueryRequest,
    dataset_service: DatasetService = Depends(get_dataset_service),
    analytics_engine: AnalyticsEngine = Depends(get_analytics_engine),
) -> QueryResponse:
    """Execute a combined query (filter, search, aggregate, sort, paginate) on a dataset."""
    try:
        df = dataset_service.get_dataframe(dataset_id)
    except DatasetNotFoundError:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")
    return analytics_engine.execute_query(df, request)


@router.post("/{dataset_id}/sql", response_model=SQLResponse)
async def sql_query(
    dataset_id: str,
    request: SQLRequest,
    dataset_service: DatasetService = Depends(get_dataset_service),
    sql_engine: SQLEngine = Depends(get_sql_engine),
) -> SQLResponse:
    """Execute a SQL SELECT query against a dataset."""
    try:
        df = dataset_service.get_dataframe(dataset_id)
    except DatasetNotFoundError:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")
    return sql_engine.execute(df, request.query)


@router.post("/{dataset_id}/chart", response_model=ChartSpec)
async def generate_chart(
    dataset_id: str,
    request: ChartRequest,
    dataset_service: DatasetService = Depends(get_dataset_service),
    chart_generator: ChartGenerator = Depends(get_chart_generator),
) -> ChartSpec:
    """Generate a Chart.js-compatible chart specification from a dataset."""
    try:
        df = dataset_service.get_dataframe(dataset_id)
    except DatasetNotFoundError:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")
    return chart_generator.generate(df, request)
