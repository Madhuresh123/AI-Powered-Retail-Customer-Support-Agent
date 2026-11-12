"""API v1 chat endpoints for AI Chat with Dataset feature."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.dependencies import (
    get_chat_history as get_chat_history_dep,
    get_chat_service,
    get_dataset_service,
)
from app.exceptions import (
    DatasetNotFoundError,
    LLMParseError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.models.chat_schemas import ChatMessage, ChatRequest, ChatResponse
from app.services.chat_history import ChatHistory
from app.services.chat_service import ChatService
from app.services.dataset_service import DatasetService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Dataset not found"},
        422: {"description": "Validation error (missing/invalid fields)"},
        502: {"description": "AI service unavailable or invalid response"},
        504: {"description": "AI service request timed out"},
    },
)
async def send_chat_message(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """Process a natural language question about a dataset.

    Accepts a dataset_id and question, translates the question into SQL,
    executes it against the dataset, and returns a natural language answer
    with supporting data.

    Returns HTTP 200 with ChatResponse on success.
    Returns HTTP 404 if dataset_id doesn't reference an existing dataset.
    Returns HTTP 422 for validation errors (missing/empty question, question too long).
    Returns HTTP 502 if AI service is unavailable or returns invalid response.
    Returns HTTP 504 if AI service request times out.
    """
    try:
        response = chat_service.process_question(request.dataset_id, request.question)
    except DatasetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except LLMTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=exc.message,
        )
    except (LLMUnavailableError, LLMParseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.message,
        )

    return response


@router.get(
    "/history",
    response_model=list[ChatMessage],
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Dataset not found"},
        422: {"description": "Missing dataset_id query parameter"},
    },
)
async def get_chat_history(
    dataset_id: str | None = Query(default=None, description="UUID of the dataset"),
    chat_history: ChatHistory = Depends(get_chat_history_dep),
    dataset_service: DatasetService = Depends(get_dataset_service),
) -> list[ChatMessage]:
    """Retrieve conversation history for a dataset.

    Returns up to 1000 messages ordered by timestamp ascending.
    Returns an empty array if no messages exist for the dataset.

    Returns HTTP 200 with JSON array of ChatMessage objects.
    Returns HTTP 422 if dataset_id query parameter is missing.
    Returns HTTP 404 if dataset_id doesn't reference an existing dataset.
    """
    if dataset_id is None or dataset_id.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="dataset_id query parameter is required",
        )

    # Validate dataset exists
    if not dataset_service.exists(dataset_id):
        raise DatasetNotFoundError(dataset_id)

    return chat_history.get_messages(dataset_id, limit=1000)


@router.delete(
    "/history",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"description": "Dataset not found"},
        422: {"description": "Missing dataset_id query parameter"},
    },
)
async def clear_chat_history(
    dataset_id: str | None = Query(default=None, description="UUID of the dataset"),
    chat_history: ChatHistory = Depends(get_chat_history_dep),
    dataset_service: DatasetService = Depends(get_dataset_service),
) -> Response:
    """Clear conversation history for a dataset.

    Removes all messages for the specified dataset.
    Returns HTTP 204 with no body on success, even if no history exists.

    Returns HTTP 204 with no body on success.
    Returns HTTP 422 if dataset_id query parameter is missing.
    Returns HTTP 404 if dataset_id doesn't reference an existing dataset.
    """
    if dataset_id is None or dataset_id.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="dataset_id query parameter is required",
        )

    # Validate dataset exists
    if not dataset_service.exists(dataset_id):
        raise DatasetNotFoundError(dataset_id)

    chat_history.clear(dataset_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
