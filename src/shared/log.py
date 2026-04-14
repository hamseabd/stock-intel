"""Structured JSON logging for Lambda + local dev.

Usage:
    from shared.log import get_logger
    logger = get_logger(__name__)
    logger.info("Processing command", command="/pnl", chat_id="123")
    logger.error("Tool failed", tool="fetch_prices", error=str(e))

In Lambda → CloudWatch receives structured JSON (easy to filter/search).
Locally → human-readable colored output.
"""

import json
import logging
import os
import sys
import time
import traceback
from typing import Any


_IS_LAMBDA = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


class StructuredFormatter(logging.Formatter):
    """JSON formatter for CloudWatch. One JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Add extra structured fields
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)
        # Add exception info
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }
        return json.dumps(log_entry, default=str)


class LocalFormatter(logging.Formatter):
    """Human-readable formatter for local development."""

    COLORS = {
        "DEBUG": "\033[90m",     # gray
        "INFO": "\033[36m",      # cyan
        "WARNING": "\033[33m",   # yellow
        "ERROR": "\033[31m",     # red
        "CRITICAL": "\033[1;31m",  # bold red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = self.formatTime(record, "%H:%M:%S")
        msg = f"{color}{ts} [{record.levelname:>7}] {record.name}: {record.getMessage()}{self.RESET}"
        if hasattr(record, "extra_fields") and record.extra_fields:
            fields = " ".join(f"{k}={v}" for k, v in record.extra_fields.items())
            msg += f" | {fields}"
        if record.exc_info and record.exc_info[0]:
            msg += f"\n{''.join(traceback.format_exception(*record.exc_info))}"
        return msg


class StructuredLogger(logging.Logger):
    """Logger that accepts keyword arguments as structured fields."""

    def _log_with_fields(self, level: int, msg: str, args: tuple, kwargs: dict) -> None:
        # Extract standard logging kwargs
        exc_info = kwargs.pop("exc_info", None)
        stack_info = kwargs.pop("stack_info", False)
        kwargs.pop("stacklevel", None)  # not used in makeRecord directly
        extra_fields = kwargs  # everything else is a structured field

        # Support standard logging positional args: logger.debug("msg %s", val)
        if args:
            try:
                msg = msg % args
            except (TypeError, ValueError):
                msg = f"{msg} {args}"

        record = self.makeRecord(
            self.name, level, "(unknown)", 0, msg, (), exc_info
        )
        record.extra_fields = extra_fields
        if stack_info:
            record.stack_info = stack_info
        self.handle(record)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self.isEnabledFor(logging.DEBUG):
            self._log_with_fields(logging.DEBUG, msg, args, kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self.isEnabledFor(logging.INFO):
            self._log_with_fields(logging.INFO, msg, args, kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self.isEnabledFor(logging.WARNING):
            self._log_with_fields(logging.WARNING, msg, args, kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self.isEnabledFor(logging.ERROR):
            self._log_with_fields(logging.ERROR, msg, args, kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self.isEnabledFor(logging.CRITICAL):
            self._log_with_fields(logging.CRITICAL, msg, args, kwargs)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger for the given module name.

    Args:
        name: Module name, typically __name__

    Returns:
        StructuredLogger with JSON (Lambda) or colored (local) output
    """
    logging.setLoggerClass(StructuredLogger)
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter() if _IS_LAMBDA else LocalFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG if os.environ.get("LOG_LEVEL") == "DEBUG" else logging.INFO)
        logger.propagate = False

    return logger


class Timer:
    """Context manager to time operations and log the duration.

    Usage:
        with Timer(logger, "fetch_prices", ticker="AMZN"):
            prices = yf.download(...)
    """

    def __init__(self, logger: StructuredLogger, operation: str, **fields: Any):
        self.logger = logger
        self.operation = operation
        self.fields = fields
        self.start = 0.0

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = round((time.time() - self.start) * 1000, 1)
        if exc_type:
            self.logger.error(
                f"{self.operation} failed",
                duration_ms=duration_ms,
                error=str(exc_val),
                error_type=exc_type.__name__,
                **self.fields,
            )
        else:
            self.logger.info(
                f"{self.operation} completed",
                duration_ms=duration_ms,
                **self.fields,
            )
        return False  # don't suppress exceptions
