"""Chat request and response schemas for the AI Chat with Dataset feature."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """POST /api/v1/chat request body."""

    dataset_id: str
    question: str = Field(..., min_length=1, max_length=1000)


class ChatDataResponse(BaseModel):
    """Structured query result data in the response."""

    columns: list[str]
    rows: list[dict]  # max 100 rows for response


class ChatResponse(BaseModel):
    """POST /api/v1/chat success response."""

    answer: str = Field(..., max_length=2000)
    sql: str | None = None
    data: ChatDataResponse | None = None
    timestamp: str  # ISO 8601 UTC


class ChatMessage(BaseModel):
    """A single conversation message."""

    role: str  # "user" or "assistant"
    content: str = Field(..., max_length=4096)
    sql: str | None = None
    data: list[dict] | None = None
    timestamp: str  # ISO 8601


class ColumnSchema(BaseModel):
    """Column schema info for prompt building."""

    name: str
    dtype: str  # "number", "string", "boolean", "date"


class QueryResult(BaseModel):
    """Result from Query_Executor."""

    columns: list[str]
    rows: list[dict]


class LLMResponse(BaseModel):
    """Parsed LLM response."""

    response_type: str  # "sql" or "answer"
    sql: str | None = None
    answer: str | None = None
