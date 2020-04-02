import asyncio
import logging
import re
from enum import Enum
from pathlib import Path
from typing import Awaitable, Callable, Tuple

import aiofiles

log = logging.getLogger(__name__)


class LogType(Enum):
    LOG = 1
    PROGRESS = 2


progress_regexp = re.compile(
    r"\[?progress[\]:]?\s*([0-1]?\.\d+|\d+(%)|\d+\s*(percent)|(\d+\/\d+))"
)


async def parse_line(line: str) -> Tuple[LogType, str]:
    # TODO: This should be 'settings', a regex for every service
    match = re.search(progress_regexp, line.lower())
    if not match:
        # default return as log
        return (LogType.LOG, f"[task] {line}")
    try:
        # can be anything from "23 percent", 23%, 23/234, 0.0-1.0
        progress = match.group(1)
        if match.group(2):
            # this is of the 23% kind
            return (
                LogType.PROGRESS,
                str(float(progress.rstrip("%").strip()) / 100.0),
            )
        if match.group(3):
            # this is of the 23 percent kind
            return (
                LogType.PROGRESS,
                str(float(progress.rstrip("percent").strip()) / 100.0),
            )
        if match.group(4):
            # this is of the 23/123 kind
            nums = progress.strip().split("/")
            return (LogType.PROGRESS, str(float(nums[0]) / float(nums[1])))
        # this is of the 0.0-1.0 kind
        return (LogType.PROGRESS, progress.strip())
    except ValueError:
        log.exception("Could not extract progress from log line %s", line)
        return (LogType.LOG, f"[task] {line}")


async def monitor_logs_task(
    log_file: Path, log_cb: Awaitable[Callable[[LogType, str], None]]
) -> None:
    try:
        log.debug("start monitoring log in %s", log_file)
        async with aiofiles.open(log_file, mode="r") as fp:
            log.debug("log monitoring: opened %s", log_file)
            await fp.seek(0, 2)
            await monitor_logs(fp, log_cb)

    except asyncio.CancelledError:
        # user cancels
        log.debug("stop monitoring log in %s", log_file)


async def monitor_logs(
    file_pointer, log_cb: Awaitable[Callable[[LogType, str], None]]
) -> None:
    while True:
        # try to read line
        line = await file_pointer.readline()
        if not line:
            asyncio.sleep(1)
            continue
        log.debug("log monitoring: found log %s", line)
        log_type, parsed_line = await parse_line(line)

        await log_cb(log_type, parsed_line)
