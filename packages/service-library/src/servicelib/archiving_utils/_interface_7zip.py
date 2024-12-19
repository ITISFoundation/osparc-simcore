import asyncio
import asyncio.subprocess
import logging
import os
import re
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Final

import tqdm
from models_library.basic_types import IDStr
from pydantic import NonNegativeInt
from servicelib.logging_utils import log_catch
from tqdm.contrib.logging import tqdm_logging_redirect

from ..progress_bar import ProgressBarData
from ._errors import ArchiveError
from ._tdqm_utils import (
    TQDM_FILE_OPTIONS,
    TQDM_MULTI_FILES_OPTIONS,
    compute_tqdm_miniters,
    human_readable_size,
)
from ._utils import iter_files_to_compress

_logger = logging.getLogger(__name__)


async def _run_cli_command(
    command: str,
    *,
    output_handlers: list[Callable[[str], Awaitable[None]]] | None = None,
) -> None:
    """
    Raises:
        ArchiveError: when it fails to execute the command
    """

    process = await asyncio.create_subprocess_shell(
        command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    async def read_stream(
        stream, chunk_size: NonNegativeInt = 16, window_size: NonNegativeInt = 16
    ) -> str:
        command_output = ""

        # Initialize buffer to store lookbehind window
        lookbehind_buffer = ""

        while True:
            chunk = await stream.read(chunk_size)
            if not chunk:
                # Process remaining buffer if any
                if lookbehind_buffer and output_handlers:
                    await asyncio.gather(
                        *[handler(lookbehind_buffer) for handler in output_handlers]
                    )
                break

            chunk = chunk.decode("utf-8")
            command_output += chunk

            # Combine lookbehind buffer with new chunk
            current_text = lookbehind_buffer + chunk

            if output_handlers:
                await asyncio.gather(
                    *[handler(current_text) for handler in output_handlers]
                )

            # Keep last window_size characters for next iteration
            lookbehind_buffer = current_text[-window_size:]

        return command_output

    # Wait for the process to complete and all output to be processed
    command_output, _ = await asyncio.gather(
        asyncio.create_task(read_stream(process.stdout)),
        process.wait(),
    )

    if process.returncode != os.EX_OK:
        msg = f"Could not run '{command}' error: '{command_output}'"
        raise ArchiveError(msg)


_TOTAL_BYTES_RE: Final[str] = r" (\d+)\s*bytes "
_FILE_COUNT_RE: Final[str] = r" (\d+)\s*files"
_PROGRESS_PERCENT_RE: Final[str] = r" (?:100|\d?\d)% "
_ALL_DONE_RE: Final[str] = r"Everything is Ok"


class ArchiveInfoParser:
    def __init__(self) -> None:
        self.total_bytes: NonNegativeInt | None = None
        self.file_count: NonNegativeInt | None = None

    async def parse_chunk(self, chunk: str) -> None:
        # search for ` NUMBER bytes ` -> set byte size
        if self.total_bytes is None and (match := re.search(_TOTAL_BYTES_RE, chunk)):
            self.total_bytes = int(match.group(1))

        # search for ` NUMBER files` -> set file count
        if self.file_count is None and (match := re.search(_FILE_COUNT_RE, chunk)):
            self.file_count = int(match.group(1))

    def get_parsed_values(self) -> tuple[NonNegativeInt, NonNegativeInt]:
        if self.total_bytes is None:
            msg = f"Unexpected value for {self.total_bytes=}. Should not be None"
            raise ArchiveError(msg)

        if self.file_count is None:
            msg = f"Unexpected value for {self.file_count=}. Should not be None"
            raise ArchiveError(msg)

        return (self.total_bytes, self.file_count)


class ProgressParser:
    def __init__(
        self, decompressed_bytes: Callable[[NonNegativeInt], Awaitable[None]]
    ) -> None:
        self.decompressed_bytes = decompressed_bytes
        self.total_bytes: NonNegativeInt | None = None

        # in range 0% -> 100%
        self.percent: NonNegativeInt | None = None
        self.finished: bool = False
        self.finished_emitted: bool = False

        self.emitted_total: NonNegativeInt = 0

    def _prase_progress(self, chunk: str) -> None:
        # search for " NUMBER bytes" -> set byte size
        if self.total_bytes is None and (match := re.search(_TOTAL_BYTES_RE, chunk)):
            self.total_bytes = int(match.group(1))

        # search for ` dd% ` -> update progress (as last entry inside the string)
        if matches := re.findall(_PROGRESS_PERCENT_RE, chunk):
            self.percent = int(matches[-1].strip().strip("%"))

        # search for `Everything is Ok` -> set 100% and finish
        if re.search(_ALL_DONE_RE, chunk, re.IGNORECASE):
            self.finished = True

    async def parse_chunk(self, chunk: str) -> None:
        self._prase_progress(chunk)

        if self.total_bytes is not None and self.percent is not None:
            # total bytes decompressed
            current_bytes_progress = int(self.percent * self.total_bytes / 100)

            # only emit an update if something changed since before
            bytes_diff = current_bytes_progress - self.emitted_total
            if self.emitted_total == 0 or bytes_diff > 0:
                await self.decompressed_bytes(bytes_diff)

            self.emitted_total = current_bytes_progress

        # if finished emit the remaining diff
        if self.total_bytes and self.finished and not self.finished_emitted:

            await self.decompressed_bytes(self.total_bytes - self.emitted_total)
            self.finished_emitted = True


async def archive_dir(
    dir_to_compress: Path,
    destination: Path,
    *,
    compress: bool,
    progress_bar: ProgressBarData | None = None,
) -> None:

    compression_option = "-mx=0" if compress else ""
    command = f"7z a -tzip -bsp1 {compression_option} {destination} {dir_to_compress}"

    folder_size_bytes = sum(
        file.stat().st_size for file in iter_files_to_compress(dir_to_compress)
    )

    async with AsyncExitStack() as stack:
        if not progress_bar:
            progress_bar = ProgressBarData(
                num_steps=1, description=IDStr(f"compressing {dir_to_compress.name}")
            )
        sub_progress = await stack.enter_async_context(
            progress_bar.sub_progress(folder_size_bytes, description=IDStr("..."))
        )

        tqdm_progress = stack.enter_context(
            tqdm_logging_redirect(
                desc=f"compressing {dir_to_compress} -> {destination}\n",
                total=folder_size_bytes,
                **(
                    TQDM_FILE_OPTIONS
                    | {"miniters": compute_tqdm_miniters(folder_size_bytes)}
                ),
            )
        )

        async def progress_handler(byte_progress: NonNegativeInt) -> None:
            tqdm_progress.update(byte_progress)
            await sub_progress.update(byte_progress)

        await _run_cli_command(
            command, output_handlers=[ProgressParser(progress_handler).parse_chunk]
        )


async def unarchive_dir(
    archive_to_extract: Path,
    destination_folder: Path,
    *,
    max_workers: int = 0,  # TODO: remove at the end not used
    progress_bar: ProgressBarData | None = None,
    log_cb: Callable[[str], Awaitable[None]] | None = None,
) -> set[Path]:
    _ = max_workers  # not required here, can be removed from the interface

    archive_info_parser = ArchiveInfoParser()
    await _run_cli_command(
        f"7z l {archive_to_extract}",
        output_handlers=[archive_info_parser.parse_chunk],
    )
    total_bytes, file_count = archive_info_parser.get_parsed_values()

    with tqdm.tqdm(
        desc=f"decompressing {archive_to_extract} -> {destination_folder} [{file_count} file{'s' if file_count > 1 else ''}"
        f"/{human_readable_size(archive_to_extract.stat().st_size)}]\n",
        total=total_bytes,
        **TQDM_MULTI_FILES_OPTIONS,
    ) as tqdm_progress:

        async def progress_handler(byte_progress: NonNegativeInt) -> None:
            if tqdm_progress.update(byte_progress) and log_cb:
                with log_catch(_logger, reraise=False):
                    await log_cb(f"{tqdm_progress}")

        await _run_cli_command(
            f"7z x -bsp1 {archive_to_extract} -o{destination_folder}",
            output_handlers=[ProgressParser(progress_handler).parse_chunk],
        )

    return {x for x in destination_folder.rglob("*") if x.is_file()}
