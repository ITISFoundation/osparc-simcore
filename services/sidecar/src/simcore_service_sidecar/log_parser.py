import asyncio
import logging
import re
import tempfile
from enum import Enum
from pathlib import Path
from typing import Awaitable, Callable, Optional, Tuple, Union

import aiodocker
import aiofiles
from aiodocker.containers import DockerContainer
from aiofile import AIOFile, Writer

from . import exceptions

log = logging.getLogger(__name__)


class LogType(Enum):
    LOG = 1
    PROGRESS = 2
    INSTRUMENTATION = 3


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
    mon_log_file_or_container: Union[Path, DockerContainer],
    log_cb: Awaitable[Callable[[LogType, str], None]],
    out_log_file: Optional[Path] = None,
) -> None:
    try:
        if isinstance(mon_log_file_or_container, Path):
            log.debug("start monitoring log in %s", mon_log_file_or_container)
            await _monitor_log_file(mon_log_file_or_container, log_cb)
        elif isinstance(mon_log_file_or_container, DockerContainer):
            log.debug("start monitoring docker logs of %s", mon_log_file_or_container)
            await _monitor_docker_container(
                mon_log_file_or_container, log_cb, out_log_file
            )
        else:
            raise exceptions.SidecarException("Invalid log type")

    except asyncio.CancelledError:
        # user cancels
        log.debug("stop monitoring logs in")


async def _monitor_docker_container(
    container: DockerContainer,
    log_cb: Awaitable[Callable[[LogType, str], None]],
    out_log_file: Optional[Path],
) -> None:
    # Avoids raising UnboundLocalError: local variable 'log_type' referenced before assignment
    log_type, parsed_line = LogType.INSTRUMENTATION, "Undefined"
    log_file = out_log_file
    if not out_log_file:
        temporary_file = tempfile.NamedTemporaryFile(delete=False, suffix=".dat")
        temporary_file.close()
        log_file = Path(temporary_file.name)

    try:
        async with AIOFile(str(log_file), "w+") as afp:
            writer = Writer(afp)
            async for line in container.log(stdout=True, stderr=True, follow=True):
                log_type, parsed_line = await parse_line(line)
                await log_cb(log_type, parsed_line)
                await writer(f"{log_type.name}: {parsed_line}")
    except aiodocker.exceptions.DockerError as e:
        log_type, parsed_line = await parse_line(
            f"Could not recover logs because: {str(e)}"
        )
        await log_cb(log_type, parsed_line)
    finally:
        # clean up
        if not out_log_file and log_file:
            log_file.unlink()


async def _monitor_log_file(
    log_file, log_cb: Awaitable[Callable[[LogType, str], None]]
) -> None:
    async with aiofiles.open(log_file, mode="r") as file_pointer:
        log.debug("log monitoring: opened %s", log_file)
        await file_pointer.seek(0, 2)
        while True:
            # try to read line
            line = await file_pointer.readline()
            if not line:
                asyncio.sleep(1)
                continue
            log.debug("log monitoring: found log %s", line)
            log_type, parsed_line = await parse_line(line)

            await log_cb(log_type, parsed_line)
