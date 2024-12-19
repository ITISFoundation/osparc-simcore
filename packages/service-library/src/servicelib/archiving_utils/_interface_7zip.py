import asyncio
import asyncio.subprocess
import logging
import os
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Final

from pydantic import NonNegativeInt

from ..progress_bar import ProgressBarData
from ._errors import ArchiveError

_logger = logging.getLogger(__name__)


async def _run_cli_command(
    command: str, output_handlers: list[Callable[[str], Awaitable[None]]] | None = None
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
    print("OUTPUT=", command_output)

    if process.returncode != os.EX_OK:
        msg = f"Could not run '{command}' error: '{command_output}'"
        raise ArchiveError(msg)


async def print_output_handler(chunk: str) -> None:
    print(f"{chunk=}")


_TOTAL_BYTES_RE: Final[str] = r" (\d+)\s*bytes "
_PROGRESS_PERCENT_RE: Final[str] = r" (?:100|\d?\d)% "
_ALL_DONE_RE: Final[str] = r"Everything is Ok"


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
        # search for "NUMBER bytes" -> set bytes size
        if self.total_bytes is None and (match := re.search(_TOTAL_BYTES_RE, chunk)):
            self.total_bytes = int(match.group(1))

        # search for `dd%` -> update progress (as last entry inside the string)
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
    store_relative_path: bool,  # always set to True  # TODO : remove at the end not used
    exclude_patterns: set[str] | None = None,  # TODO : remove at the end not used
    progress_bar: ProgressBarData | None = None,
) -> None:
    assert store_relative_path is True  # nosec

    compression_option = "-mx=0" if compress else ""
    command = f"7z a -tzip -bsp1 {compression_option} {destination} {dir_to_compress}"

    async def progress_handler(byte_progress: NonNegativeInt) -> None:
        print(f"{byte_progress=}")

    parser = ProgressParser(progress_handler)
    await _run_cli_command(
        command,
        [
            #   print_output_handler,
            parser.parse_chunk,
        ],
    )


async def unarchive_dir(
    archive_to_extract: Path,
    destination_folder: Path,
    *,
    max_workers: int = 0,  # TODO: remove at the end not used
    progress_bar: ProgressBarData | None = None,
    log_cb: Callable[[str], Awaitable[None]] | None = None,
) -> set[Path]:
    # NOTE: maintained here conserve the interface
    _ = max_workers  # no longer used

    command = f"7z x -bsp1 {archive_to_extract} -o{destination_folder}"

    await _run_cli_command(command, [print_output_handler])

    return set()
