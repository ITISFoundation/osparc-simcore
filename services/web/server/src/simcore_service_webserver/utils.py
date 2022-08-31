"""
    General utilities and helper functions
"""
import asyncio
import hashlib
import logging
import os
import sys
import tracemalloc
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

import orjson
from models_library.basic_types import SHA1Str
from servicelib.error_codes import ErrorCodeStr

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
log = logging.getLogger(__name__)


def is_osparc_repo_dir(path: Path) -> bool:
    return all(
        any(path.glob(expression)) for expression in [".github", "packages", "services"]
    )


def search_osparc_repo_dir(max_iter=8):
    """Returns path to root repo dir or None

    NOTE: assumes this file within repo, i.e. only happens in edit mode!
    """
    root_dir = CURRENT_DIR
    if "services/web/server" in str(root_dir):
        it = 1
        while not is_osparc_repo_dir(root_dir) and it < max_iter:
            root_dir = root_dir.parent
            it += 1

        if is_osparc_repo_dir(root_dir):
            return root_dir
    return None


def gravatar_hash(email: str) -> str:
    return hashlib.md5(email.lower().encode("utf-8")).hexdigest()  # nosec


# -----------------------------------------------
#
# DATE/TIME
#
#

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

SECOND: int = 1
MINUTE: int = 60 * SECOND  # secs
HOUR: int = 60 * MINUTE  # secs
DAY: int = 24 * HOUR  # sec


def now() -> datetime:
    return datetime.utcnow()


def format_datetime(snapshot: datetime) -> str:
    # return snapshot.strftime(DATETIME_FORMAT)
    # TODO: this fullfills datetime schema!!!
    # 'pattern': '\\d{4}-(12|11|10|0?[1-9])-(31|30|[0-2]?\\d)T(2[0-3]|1\\d|0?[1-9])(:(\\d|[0-5]\\d)){2}(\\.\\d{3})?Z',

    # FIXME: ensure snapshot is ZULU time!
    return "{}Z".format(snapshot.isoformat(timespec="milliseconds"))


def now_str() -> str:
    """Returns formatted time snapshot in UTC"""
    return format_datetime(now())


def to_datetime(snapshot: str) -> datetime:
    #
    return datetime.strptime(snapshot, DATETIME_FORMAT)


# -----------------------------------------------
#
# PROFILING
#
# Based on
#   - https://tech.gadventures.com/hunting-for-memory-leaks-in-asyncio-applications-3614182efaf7


def get_task_info(task: asyncio.Task) -> dict:
    def _format_frame(f):
        keys = ["f_code", "f_lineno"]
        return OrderedDict([(k, str(getattr(f, k))) for k in keys])

    info = OrderedDict(
        txt=str(task),
        type=str(type(task)),
        done=task.done(),
        cancelled=False,
        stack=[],
        exception=None,
    )

    if not task.done():
        info["stack"] = [_format_frame(x) for x in task.get_stack()]
    else:
        if task.cancelled():
            info["cancelled"] = True
        else:
            # WARNING: raise if not done or cancelled
            exc = task.exception()
            info["exception"] = f"{type(exc)}: {str(exc)}" if exc else None
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
        log.warning(
            "Cannot take snapshot. Forgot to start tracing? PYTHONTRACEMALLOC=%s",
            os.environ.get("PYTHONTRACEMALLOC"),
        )

    return top_trace


def compose_support_error_msg(
    msg: str, error_code: ErrorCodeStr, support_email: str = "support"
) -> str:
    return (
        f"{msg.strip(' .').capitalize()} [{error_code}].\n"
        f"Please contact {support_email} and attach the message above"
    )


# -----------------------------------------------
#
# FORMATTING
#


# -----------------------------------------------
#
# SERIALIZATION, CHECKSUMS,
#


def compute_sha1_on_small_dataset(d: Any) -> SHA1Str:
    """
    This should be used for small datasets, otherwise it should be chuncked
    and aggregated

    More details in test_utils.py:test_compute_sha1_on_small_dataset
    """
    # SEE options in https://github.com/ijl/orjson#option
    data_bytes = orjson.dumps(d, option=orjson.OPT_NON_STR_KEYS | orjson.OPT_SORT_KEYS)
    return hashlib.sha1(data_bytes).hexdigest()  # nosec
