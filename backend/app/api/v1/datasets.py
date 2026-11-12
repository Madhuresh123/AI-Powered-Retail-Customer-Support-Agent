"""API v1 dataset endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Path, Response, UploadFile, status

from app.dependencies import get_csv_parser, get_dataset_service, get_preview_engine, get_rest_importer
from app.exceptions import DatasetNotFoundError
from app.models.dataset import DatasetMetadata, SourceType
from app.models.schemas import (
    ColumnDescriptor,
    DatasetDetail,
    DatasetListItem,
    ImportRequest,
    ImportResponse,
    PreviewResponse,
    SummaryResponse,
    UploadResponse,
)
from app.services.csv_parser import CSVParser
from app.services.dataset_service import DatasetService
from app.services.preview_engine import PreviewEngine
from app.services.rest_importer import RESTImporter

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _validate_dataset_id(dataset_id: str) -> None:
    """Validate that dataset_id is a valid UUID format.

    Raises HTTPException 422 if the format is invalid.
    """
    try:
        uuid.UUID(dataset_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid dataset_id format: '{dataset_id}' is not a valid UUID",
        )


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Invalid CSV format, encoding, or structure"},
        413: {"description": "File exceeds 50 MB"},
        422: {"description": "No file provided"},
    },
)
async def upload_csv(
    file: UploadFile = File(...),
    csv_parser: CSVParser = Depends(get_csv_parser),
    dataset_service: DatasetService = Depends(get_dataset_service),
) -> UploadResponse:
    """Upload a CSV file to create a new dataset.

    Accepts a multipart file upload, validates and parses the CSV,
    stores it in the dataset store, and returns metadata about the
    created dataset.

    Returns HTTP 201 with dataset_id, name, and row_count on success.
    Returns HTTP 422 if no file is provided.
    Returns HTTP 400 for invalid CSV format, encoding, empty data, or too many columns.
    Returns HTTP 413 if file exceeds 50 MB.
    """
    if file.filename is None or file.filename == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No file provided in the upload request",
        )

    # Parse and validate the CSV file
    parse_result = await csv_parser.parse(file)

    # Build metadata for storage
    metadata = DatasetMetadata(
        dataset_id="",  # Will be overwritten by DatasetService.store()
        name=parse_result.filename,
        row_count=parse_result.row_count,
        column_count=parse_result.column_count,
        source_type=SourceType.CSV,
        source_url=None,
        created_at=datetime.now(timezone.utc),
        file_size_bytes=0,  # Will be updated after Parquet write
    )

    # Store the dataset
    dataset_id = dataset_service.store(parse_result.dataframe, metadata)

    return UploadResponse(
        dataset_id=dataset_id,
        name=parse_result.filename,
        row_count=parse_result.row_count,
    )


@router.post(
    "/import-api",
    response_model=ImportResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        422: {"description": "Invalid URL or unsupported response format"},
        413: {"description": "Response payload exceeds 50 MB"},
        502: {"description": "Upstream connection failure or timeout"},
    },
)
async def import_from_api(
    body: ImportRequest,
    rest_importer: RESTImporter = Depends(get_rest_importer),
    dataset_service: DatasetService = Depends(get_dataset_service),
) -> ImportResponse:
    """
    Import a dataset from an external REST API.

    Fetches data from the provided URL, normalizes the JSON response into
    tabular format, and stores it as a dataset.
    """
    result = await rest_importer.import_from_url(body.url)

    # Build metadata for storage
    metadata = DatasetMetadata(
        dataset_id="",  # Will be assigned by DatasetService.store()
        name=f"api_import_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        row_count=result.row_count,
        column_count=len(result.dataframe.columns),
        source_type=SourceType.API,
        source_url=result.source_url,
        created_at=datetime.now(timezone.utc),
        file_size_bytes=0,  # Will be updated by DatasetService.store()
    )

    dataset_id = dataset_service.store(result.dataframe, metadata)

    return ImportResponse(
        dataset_id=dataset_id,
        source_url=result.source_url,
        row_count=result.row_count,
    )


@router.get(
    "",
    response_model=list[DatasetListItem],
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Dataset store unavailable"},
    },
)
async def list_datasets(
    dataset_service: DatasetService = Depends(get_dataset_service),
) -> list[DatasetListItem]:
    """
    List all datasets.

    Returns a JSON array of all stored datasets with their metadata,
    ordered by creation timestamp descending (most recent first).
    Returns an empty array if no datasets exist.
    """
    try:
        datasets = dataset_service.list_all()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve datasets: data store is unavailable",
        )

    return [
        DatasetListItem(
            dataset_id=ds.dataset_id,
            name=ds.name,
            row_count=ds.row_count,
            created_at=ds.created_at,
        )
        for ds in datasets
    ]


@router.get(
    "/{dataset_id}",
    response_model=DatasetDetail,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Dataset not found"},
        422: {"description": "Invalid dataset ID format"},
    },
)
async def get_dataset_detail(
    dataset_id: str = Path(..., description="UUID of the dataset"),
    dataset_service: DatasetService = Depends(get_dataset_service),
) -> DatasetDetail:
    """
    Get detailed metadata for a specific dataset.

    Returns dataset_id, name, row_count, column_count, created_at,
    and source_type for the specified dataset.
    """
    _validate_dataset_id(dataset_id)

    metadata = dataset_service.get_metadata(dataset_id)

    return DatasetDetail(
        dataset_id=metadata.dataset_id,
        name=metadata.name,
        row_count=metadata.row_count,
        column_count=metadata.column_count,
        created_at=metadata.created_at,
        source_type=metadata.source_type,
    )


@router.delete(
    "/{dataset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        400: {"description": "Malformed dataset ID"},
        404: {"description": "Dataset not found"},
    },
)
async def delete_dataset(
    dataset_id: str = Path(..., description="UUID of the dataset"),
    dataset_service: DatasetService = Depends(get_dataset_service),
) -> Response:
    """
    Delete a dataset.

    Removes the specified dataset's stored file data and metadata
    from the dataset store. Returns 204 with no body on success.
    """
    try:
        uuid.UUID(dataset_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed dataset_id: '{dataset_id}' is not a valid identifier",
        )

    dataset_service.delete(dataset_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{dataset_id}/preview",
    response_model=PreviewResponse,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Dataset not found"},
    },
)
async def get_dataset_preview(
    dataset_id: str = Path(..., description="UUID of the dataset"),
    preview_engine: PreviewEngine = Depends(get_preview_engine),
) -> PreviewResponse:
    """
    Preview the first 20 rows of a dataset.

    Returns column headers and row data keyed by column name.
    """
    return preview_engine.get_preview(dataset_id)


@router.get(
    "/{dataset_id}/columns",
    response_model=list[ColumnDescriptor],
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Dataset not found"},
    },
)
async def get_dataset_columns(
    dataset_id: str = Path(..., description="UUID of the dataset"),
    preview_engine: PreviewEngine = Depends(get_preview_engine),
) -> list[ColumnDescriptor]:
    """
    Get column names and inferred data types for a dataset.

    Returns column descriptors in the same order as the columns appear in the dataset.
    """
    return preview_engine.get_columns(dataset_id)


@router.get(
    "/{dataset_id}/summary",
    response_model=SummaryResponse,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Dataset not found"},
    },
)
async def get_dataset_summary(
    dataset_id: str = Path(..., description="UUID of the dataset"),
    preview_engine: PreviewEngine = Depends(get_preview_engine),
) -> SummaryResponse:
    """
    Get statistical summary for a dataset.

    Returns row count, column count, missing value count, duplicate row count,
    and memory usage in bytes.
    """
    return preview_engine.get_summary(dataset_id)
