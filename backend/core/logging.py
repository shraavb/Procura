"""
Structured logging configuration for production.
Follows FastAPI best practices for LLM applications.
"""
import logging
import sys
import json
from datetime import datetime
from typing import Any
from contextvars import ContextVar
import traceback

from config import get_settings

settings = get_settings()

# Context variables for request tracing
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add context variables
        if request_id := request_id_ctx.get():
            log_data["request_id"] = request_id
        if user_id := user_id_ctx.get():
            log_data["user_id"] = user_id

        # Add extra fields
        if hasattr(record, "extra"):
            log_data["extra"] = record.extra

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }

        return json.dumps(log_data, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        request_id = request_id_ctx.get()
        rid_str = f"[{request_id[:8]}] " if request_id else ""

        return (
            f"{color}{record.levelname:8}{self.RESET} "
            f"{datetime.utcnow().strftime('%H:%M:%S')} "
            f"{rid_str}"
            f"{record.name}: {record.getMessage()}"
        )


def setup_logging() -> None:
    """Configure logging based on settings."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    # Set formatter based on config
    if settings.log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(TextFormatter())

    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)


class LogContext:
    """Context manager for adding metadata to log messages."""

    def __init__(self, **kwargs: Any):
        self.kwargs = kwargs
        self._tokens: list = []

    def __enter__(self) -> "LogContext":
        if "request_id" in self.kwargs:
            self._tokens.append(("request_id", request_id_ctx.set(self.kwargs["request_id"])))
        if "user_id" in self.kwargs:
            self._tokens.append(("user_id", user_id_ctx.set(self.kwargs["user_id"])))
        return self

    def __exit__(self, *args: Any) -> None:
        for name, token in self._tokens:
            if name == "request_id":
                request_id_ctx.reset(token)
            elif name == "user_id":
                user_id_ctx.reset(token)


class ContextLogger(logging.LoggerAdapter):
    """Logger adapter that includes context in all messages."""

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        extra = kwargs.get("extra", {})
        if request_id := request_id_ctx.get():
            extra["request_id"] = request_id
        if user_id := user_id_ctx.get():
            extra["user_id"] = user_id
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(name: str) -> ContextLogger:
    """Get a context-aware logger."""
    return ContextLogger(logging.getLogger(name), {})
