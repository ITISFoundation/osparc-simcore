"""
General utilities and helper functions
"""

import asyncio
import logging
import os
import tracemalloc
from datetime import datetime

from common_library.error_codes import ErrorCodeStr
from typing_extensions import (  # https://docs.pydantic.dev/latest/api/standard_library_types/#typeddict
    TypedDict,
)

_logger = logging.getLogger(__name__)

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

SECOND: int = 1
MINUTE: int = 60 * SECOND  # secs
HOUR: int = 60 * MINUTE  # secs
DAY: int = 24 * HOUR  # sec


def now() -> datetime:
    return datetime.utcnow()


def format_datetime(snapshot: datetime) -> str:
    # FIXME: ensure snapshot is ZULU time!
    return "{}Z".format(snapshot.isoformat(timespec="milliseconds"))


def now_str() -> str:
    """Returns formatted time snapshot in UTC"""
    return format_datetime(now())


def to_datetime(snapshot: str) -> datetime:
    return datetime.strptime(snapshot, DATETIME_FORMAT)


# -----------------------------------------------
#
# PROFILING
#
# Based on
#   - https://tech.gadventures.com/hunting-for-memory-leaks-in-asyncio-applications-3614182efaf7


class StackInfoDict(TypedDict):
    f_code: str
    f_lineno: str


class TaskInfoDict(TypedDict):
    txt: str
    type: str
    done: bool
    cancelled: bool
    stack: list[StackInfoDict]
    exception: str | None


def get_task_info(task: asyncio.Task) -> TaskInfoDict:
    def _format_frame(f):
        return StackInfoDict(f_code=str(f.f_code), f_lineno=str(f.f_lineno))

    info = TaskInfoDict(
        txt=str(task),
        type=str(type(task)),
        done=task.done(),
        cancelled=False,
        stack=[],
        exception=None,
    )

    if not task.done():
        info["stack"] = [_format_frame(x) for x in task.get_stack()]
    elif task.cancelled():
        info["cancelled"] = True
    else:
        # WARNING: raise if not done or cancelled
        exc = task.exception()
        info["exception"] = f"{type(exc)}: {exc!s}" if exc else None
    return info


def get_tracemalloc_info(top=10) -> list[str]:
    # Set PYTHONTRACEMALLOC=1 to start tracing
    #
    #
    # SEE https://docs.python.org/3.6/library/tracemalloc.html
    top_trace = []
    if tracemalloc.is_tracing():
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics("lineno")
        top = min(abs(top), len(top_stats))
        top_trace = [str(x) for x in top_stats[:top]]
    else:
        _logger.warning(
            "Cannot take snapshot. Forgot to start tracing? PYTHONTRACEMALLOC=%s",
            os.environ.get("PYTHONTRACEMALLOC"),
        )

    return top_trace


def compose_support_error_msg(
    msg: str, error_code: ErrorCodeStr, support_email: str = "support"
) -> str:
    sentences = [
        sentence[0].upper() + sentence[1:]
        for line in msg.split("\n")
        if (sentence := line.strip(" ."))
    ]
    sentences.append(
        f"For more information please forward this message to {support_email} (supportID={error_code})"
    )

    return ". ".join(sentences)
