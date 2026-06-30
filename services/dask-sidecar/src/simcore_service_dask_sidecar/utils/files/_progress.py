import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from typing import Any, Final

from pydantic import ByteSize
from servicelib.logging_utils import LogLevelInt, LogMessageStr

LogPublishingCB = Callable[[LogMessageStr, LogLevelInt], Coroutine[Any, Any, None]]


def _format_progress_message(
    *,
    text_prefix: str,
    bytes_transferred: int,
    file_size: int | None,
    elapsed_time: float,
) -> str:
    speed_mbps = ByteSize(bytes_transferred).to("MB") / elapsed_time if elapsed_time > 0 else 0.0
    return (
        f"{text_prefix}"
        f" {100.0 * float(bytes_transferred or 0) / float(file_size or 1):.1f}%"
        f" ({ByteSize(bytes_transferred).human_readable() if bytes_transferred else 0} / "
        f"{ByteSize(file_size).human_readable() if file_size else 'NaN'})"
        f" [{speed_mbps:.2f} MBytes/s (avg)]"
    )


def _file_progress_cb(
    size,
    value,
    log_publishing_cb: LogPublishingCB,
    text_prefix: str,
    main_loop: asyncio.AbstractEventLoop,
    **kwargs,  # noqa: ARG001
):
    value_readable = ByteSize(value).human_readable() if value else 0
    size_readable = ByteSize(size).human_readable() if size else "NaN"
    asyncio.run_coroutine_threadsafe(
        log_publishing_cb(
            f"{text_prefix} {100.0 * float(value or 0) / float(size or 1):.1f}% ({value_readable} / {size_readable})",
            logging.DEBUG,
        ),
        main_loop,
    )


class _ThreadSafeProgressLogger:
    """Thread-safe progress callback for blocking transfers run in an executor.

    The callback is invoked from a worker thread with the cumulative number of
    data bytes processed so far, and schedules throttled progress logs back onto
    the main event loop via ``asyncio.run_coroutine_threadsafe``.
    """

    _MIN_PERCENT_DELTA: Final[float] = 1.0
    _MIN_INTERVAL_SECONDS: Final[float] = 1.0

    def __init__(
        self,
        *,
        file_size: int | None,
        log_publishing_cb: LogPublishingCB,
        text_prefix: str,
        main_loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._file_size = file_size
        self._log_publishing_cb = log_publishing_cb
        self._text_prefix = text_prefix
        self._main_loop = main_loop
        self._start_time = time.monotonic()
        self._last_emit_time = self._start_time
        self._last_logged_percent = -1.0
        self._bytes_processed = 0

    def __call__(self, bytes_processed: int) -> None:
        # NOTE: invoked from the executor worker thread
        self._bytes_processed = bytes_processed
        now = time.monotonic()
        percent = 100.0 * float(bytes_processed) / float(self._file_size) if self._file_size else 0.0
        enough_progress = percent - self._last_logged_percent >= self._MIN_PERCENT_DELTA
        enough_time = now - self._last_emit_time >= self._MIN_INTERVAL_SECONDS
        if not (enough_progress or enough_time):
            return
        self._last_logged_percent = percent
        self._last_emit_time = now
        asyncio.run_coroutine_threadsafe(
            self._log_publishing_cb(self._build_message(now), logging.DEBUG),
            self._main_loop,
        )

    async def emit_final(self) -> None:
        # NOTE: called on completion from the main event loop
        await self._log_publishing_cb(self._build_message(time.monotonic()), logging.DEBUG)

    def _build_message(self, now: float) -> str:
        return _format_progress_message(
            text_prefix=self._text_prefix,
            bytes_transferred=self._bytes_processed,
            file_size=self._file_size,
            elapsed_time=now - self._start_time,
        )
