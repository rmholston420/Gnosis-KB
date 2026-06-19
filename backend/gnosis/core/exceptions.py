"""Custom exception classes and FastAPI exception handlers."""

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


class NoteNotFoundError(HTTPException):
    """Raised when a requested note does not exist."""

    def __init__(self, note_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note '{note_id}' not found",
        )


class NoteConflictError(HTTPException):
    """Raised when a note with the same title/slug already exists."""

    def __init__(self, title: str) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A note with title '{title}' already exists",
        )


class VaultWriteError(HTTPException):
    """Raised when writing to the vault filesystem fails."""

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write vault file '{path}': {reason}",
        )


class LLMUnavailableError(HTTPException):
    """Raised when no LLM provider is available."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No LLM provider is currently available. Configure Ollama or an external API key.",
        )


async def gnosis_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled errors."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Internal server error: {exc!s}"},
    )
