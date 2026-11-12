from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.analytics import router as analytics_router
from app.api.v1.chat import router as chat_router
from app.api.v1.datasets import router as datasets_router
from app.exceptions import (
    AnalyticsValidationError,
    DatasetNotFoundError,
    EmptyDataError,
    FileTooLargeError,
    InvalidCSVError,
    InvalidEncodingError,
    InvalidURLError,
    LLMParseError,
    LLMTimeoutError,
    LLMUnavailableError,
    PayloadTooLargeError,
    QueryExecutionError,
    QueryValidationError,
    TooManyColumnsError,
    UnsupportedFormatError,
    UpstreamError,
)

import os

app = FastAPI(
    title="Data Insight API",
    description="RESTful API for dataset management and data preview",
    version="1.0.0",
)

# Initialize database tables if using Postgres
if os.environ.get("DATABASE_URL"):
    try:
        from app.database import init_db
        init_db()
    except Exception as e:
        print(f"Warning: Database init failed: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Global Exception Handlers ---


@app.exception_handler(DatasetNotFoundError)
async def dataset_not_found_handler(request: Request, exc: DatasetNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(FileTooLargeError)
async def file_too_large_handler(request: Request, exc: FileTooLargeError):
    return JSONResponse(status_code=413, content={"detail": str(exc)})


@app.exception_handler(InvalidCSVError)
async def invalid_csv_handler(request: Request, exc: InvalidCSVError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(InvalidEncodingError)
async def invalid_encoding_handler(request: Request, exc: InvalidEncodingError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(EmptyDataError)
async def empty_data_handler(request: Request, exc: EmptyDataError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(TooManyColumnsError)
async def too_many_columns_handler(request: Request, exc: TooManyColumnsError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(InvalidURLError)
async def invalid_url_handler(request: Request, exc: InvalidURLError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(UpstreamError)
async def upstream_error_handler(request: Request, exc: UpstreamError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(PayloadTooLargeError)
async def payload_too_large_handler(request: Request, exc: PayloadTooLargeError):
    return JSONResponse(status_code=413, content={"detail": str(exc)})


@app.exception_handler(UnsupportedFormatError)
async def unsupported_format_handler(request: Request, exc: UnsupportedFormatError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(AnalyticsValidationError)
async def analytics_validation_error_handler(request: Request, exc: AnalyticsValidationError):
    return JSONResponse(status_code=400, content={"detail": exc.message})


@app.exception_handler(QueryValidationError)
async def query_validation_error_handler(request: Request, exc: QueryValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.message})


@app.exception_handler(QueryExecutionError)
async def query_execution_error_handler(request: Request, exc: QueryExecutionError):
    return JSONResponse(status_code=422, content={"detail": exc.message})


@app.exception_handler(LLMUnavailableError)
async def llm_unavailable_error_handler(request: Request, exc: LLMUnavailableError):
    return JSONResponse(status_code=502, content={"detail": exc.message})


@app.exception_handler(LLMTimeoutError)
async def llm_timeout_error_handler(request: Request, exc: LLMTimeoutError):
    return JSONResponse(status_code=504, content={"detail": exc.message})


@app.exception_handler(LLMParseError)
async def llm_parse_error_handler(request: Request, exc: LLMParseError):
    return JSONResponse(status_code=502, content={"detail": exc.message})


# --- Routes ---


# --- Router Registration ---

app.include_router(datasets_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
