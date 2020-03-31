import asyncio
import logging
from enum import Enum
from pathlib import Path
from typing import Callable, Tuple, Awaitable

import aiofiles

log = logging.getLogger(__name__)


class LogType(Enum):
    LOG = 1
    PROGRESS = 2


async def parse_line(line: str) -> Tuple[LogType, str]:
    # TODO: This should be 'settings', a regex for every service
    if line.lower().startswith("[progress]"):
        return (LogType.PROGRESS, line.lower().lstrip("[progress]").rstrip("%").strip())

    if "percent done" in line.lower():
        progress = line.lower().rstrip("percent done")
        try:
            return (LogType.PROGRESS, str(float(progress) / 100.0))
        except ValueError:
            log.exception("Could not extract progress from log line %s", line)
    # default return as log
    return (LogType.LOG, line)


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
