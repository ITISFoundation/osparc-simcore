import asyncio
import asyncio.subprocess
import logging
import os
import re
import shlex
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Final

import tqdm
from pydantic import NonNegativeInt
from tqdm.contrib.logging import tqdm_logging_redirect

from ..file_utils import shutil_move
from ..logging_utils import log_catch
from ..progress_bar import ProgressBarData
from ._errors import (
    CouldNotFindValueError,
    CouldNotRunCommandError,
    TableHeaderNotFoundError,
)
from ._tdqm_utils import (
    TQDM_FILE_OPTIONS,
    TQDM_MULTI_FILES_OPTIONS,
    compute_tqdm_miniters,
    human_readable_size,
)
from ._utils import iter_files_to_compress

_logger = logging.getLogger(__name__)

_TOTAL_BYTES_RE: Final[re.Pattern] = re.compile(r" (\d+)\s*bytes")
_FILE_COUNT_RE: Final[re.Pattern] = re.compile(r" (\d+)\s*files")
_PROGRESS_FIND_PERCENT_RE: Final[re.Pattern] = re.compile(r" (?:100|\d?\d)% ")
_PROGRESS_EXTRACT_PERCENT_RE: Final[re.Pattern] = re.compile(r" (\d+)% ")
_ALL_DONE_RE: Final[re.Pattern] = re.compile(r"Everything is Ok", re.IGNORECASE)

_TOKEN_TABLE_HEADER_START: Final[str] = "------------------- "

_7ZIP_EXECUTABLE: Final[Path] = Path("/usr/bin/7z")


class _7ZipArchiveInfoParser:  # noqa: N801
    def __init__(self) -> None:
        self.total_bytes: NonNegativeInt | None = None
        self.file_count: NonNegativeInt | None = None

    async def parse_chunk(self, chunk: str) -> None:
        # search for ` NUMBER bytes ` -> set byte size
        if self.total_bytes is None and (match := _TOTAL_BYTES_RE.search(chunk)):
            self.total_bytes = int(match.group(1))

        # search for ` NUMBER files` -> set file count
        if self.file_count is None and (match := _FILE_COUNT_RE.search(chunk)):
            self.file_count = int(match.group(1))

    def get_parsed_values(self) -> tuple[NonNegativeInt, NonNegativeInt]:
        if self.total_bytes is None:
            raise CouldNotFindValueError(field_name="total_bytes")

        if self.file_count is None:
            raise CouldNotFindValueError(field_name="file_count")

        return (self.total_bytes, self.file_count)


class _7ZipProgressParser:  # noqa: N801
    def __init__(
        self, progress_handler: Callable[[NonNegativeInt], Awaitable[None]]
    ) -> None:
        self.progress_handler = progress_handler
        self.total_bytes: NonNegativeInt | None = None

        # in range 0% -> 100%
        self.percent: NonNegativeInt | None = None
        self.finished: bool = False
        self.finished_emitted: bool = False

        self.emitted_total: NonNegativeInt = 0

    def _parse_progress(self, chunk: str) -> None:
        # search for " NUMBER bytes" -> set byte size
        if self.total_bytes is None and (match := _TOTAL_BYTES_RE.search(chunk)):
            self.total_bytes = int(match.group(1))

        # search for ` dd% ` -> update progress (as last entry inside the string)
        if matches := _PROGRESS_FIND_PERCENT_RE.findall(chunk):  # noqa: SIM102
            if percent_match := _PROGRESS_EXTRACT_PERCENT_RE.search(matches[-1]):
                self.percent = int(percent_match.group(1))

        # search for `Everything is Ok` -> set 100% and finish
        if _ALL_DONE_RE.search(chunk):
            self.finished = True

    async def parse_chunk(self, chunk: str) -> None:
        self._parse_progress(chunk)

        if self.total_bytes is not None and self.percent is not None:
            # total bytes decompressed
            current_bytes_progress = int(self.percent * self.total_bytes / 100)

            # only emit an update if something changed since before
            bytes_diff = current_bytes_progress - self.emitted_total
            if self.emitted_total == 0 or bytes_diff > 0:
                await self.progress_handler(bytes_diff)

            self.emitted_total = current_bytes_progress

        # if finished emit the remaining diff
        if self.total_bytes and self.finished and not self.finished_emitted:

            await self.progress_handler(self.total_bytes - self.emitted_total)
            self.finished_emitted = True


async def _stream_output_reader(
    stream: asyncio.StreamReader,
    *,
    output_handler: Callable[[str], Awaitable[None]] | None,
    chunk_size: NonNegativeInt = 16,
    lookbehind_buffer_size: NonNegativeInt = 40,
) -> str:
    # NOTE: content is not read line by line but chunk by chunk to avoid missing progress updates
    # small chunks are read and of size `chunk_size` and a bigger chunk of
    # size `lookbehind_buffer_size` + `chunk_size` is emitted
    # The goal is to not split any important search in half, thus giving a change to the
    #  `output_handlers` to properly handle it

    # NOTE: at the time of writing this, the biggest possible thing to capture search would be:
    # ~`9.1TiB` -> literally ` 9999999999999 bytes ` equal to 21 characters to capture,
    # with the above defaults we the "emitted chunk" is more than double in size
    # There are no foreseeable issued due to the size of inputs to be captured.

    command_output = ""
    lookbehind_buffer = ""

    while True:
        read_chunk = await stream.read(chunk_size)

        if not read_chunk:
            # process remaining buffer if any
            if lookbehind_buffer and output_handler:
                await output_handler(lookbehind_buffer)
            break

        # `errors=replace`: avoids getting stuck when can't parse utf-8
        chunk = read_chunk.decode("utf-8", errors="replace")

        command_output += chunk
        chunk_to_emit = lookbehind_buffer + chunk
        lookbehind_buffer = chunk_to_emit[-lookbehind_buffer_size:]

        if output_handler:
            await output_handler(chunk_to_emit)

    return command_output


async def _run_cli_command(
    command: str,
    *,
    output_handler: Callable[[str], Awaitable[None]] | None = None,
) -> str:
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
    assert process.stdout  # nosec

    command_output, _ = await asyncio.gather(
        asyncio.create_task(
            _stream_output_reader(process.stdout, output_handler=output_handler)
        ),
        process.wait(),
    )

    if process.returncode != os.EX_OK:
        raise CouldNotRunCommandError(command=command, command_output=command_output)

    return command_output


async def archive_dir(
    dir_to_compress: Path,
    destination: Path,
    *,
    compress: bool,
    progress_bar: ProgressBarData | None = None,
) -> None:
    if progress_bar is None:
        progress_bar = ProgressBarData(
            num_steps=1, description=f"compressing {dir_to_compress.name}"
        )

    options = " ".join(
        [
            "a",  # archive
            "-tzip",  # type of archive
            "-bsp1",  # used for parsing progress
            f"-mx={9 if compress else 0}",  # compression level
            # guarantees archive reproducibility
            "-r",  # recurse into subdirectories if needed.
            "-mtm=off",  # Don't store last modification time
            "-mtc=off",  # Don't store file creation time
            "-mta=off",  # Don't store file access time
        ]
    )
    command = f"{_7ZIP_EXECUTABLE} {options} {shlex.quote(f'{destination}')} {shlex.quote(f'{dir_to_compress}')}/*"

    folder_size_bytes = sum(
        file.stat().st_size for file in iter_files_to_compress(dir_to_compress)
    )

    async with AsyncExitStack() as exit_stack:
        sub_progress = await exit_stack.enter_async_context(
            progress_bar.sub_progress(folder_size_bytes, description="...")
        )

        tqdm_progress = exit_stack.enter_context(
            tqdm_logging_redirect(
                desc=f"compressing {dir_to_compress} -> {destination}\n",
                total=folder_size_bytes,
                **(
                    TQDM_FILE_OPTIONS
                    | {"miniters": compute_tqdm_miniters(folder_size_bytes)}
                ),
            )
        )

        async def _compressed_bytes(byte_progress: NonNegativeInt) -> None:
            tqdm_progress.update(byte_progress)
            await sub_progress.update(byte_progress)

        await _run_cli_command(
            command, output_handler=_7ZipProgressParser(_compressed_bytes).parse_chunk
        )

        # 7zip automatically adds .zip extension if it's missing form the archive name
        if not destination.exists():
            await shutil_move(f"{destination}.zip", destination)


def _is_folder(line: str) -> bool:
    folder_attribute = line[20]
    return folder_attribute == "D"


def _extract_file_names_from_archive(command_output: str) -> set[str]:
    file_name_start: NonNegativeInt | None = None

    entries_lines: list[str] = []
    can_add_to_entries: bool = False

    # extract all lines containing files or folders
    for line in command_output.splitlines():
        if line.startswith(_TOKEN_TABLE_HEADER_START):
            file_name_start = line.rfind(" ") + 1
            can_add_to_entries = not can_add_to_entries
            continue

        if can_add_to_entries:
            entries_lines.append(line)

    file_lines: list[str] = [line for line in entries_lines if not _is_folder(line)]

    if file_lines and file_name_start is None:
        raise TableHeaderNotFoundError(
            file_lines=file_lines, command_output=command_output
        )

    return {line[file_name_start:] for line in file_lines}


async def unarchive_dir(
    archive_to_extract: Path,
    destination_folder: Path,
    *,
    progress_bar: ProgressBarData | None = None,
    log_cb: Callable[[str], Awaitable[None]] | None = None,
) -> set[Path]:
    if progress_bar is None:
        progress_bar = ProgressBarData(
            num_steps=1, description=f"extracting {archive_to_extract.name}"
        )

    # get archive information
    archive_info_parser = _7ZipArchiveInfoParser()
    list_output = await _run_cli_command(
        f"{_7ZIP_EXECUTABLE} l {shlex.quote(f'{archive_to_extract}')}",
        output_handler=archive_info_parser.parse_chunk,
    )
    file_names_in_archive = _extract_file_names_from_archive(list_output)
    total_bytes, file_count = archive_info_parser.get_parsed_values()

    async with AsyncExitStack() as exit_stack:
        sub_prog = await exit_stack.enter_async_context(
            progress_bar.sub_progress(steps=total_bytes, description="...")
        )

        tqdm_progress = exit_stack.enter_context(
            tqdm.tqdm(
                desc=f"decompressing {archive_to_extract} -> {destination_folder} [{file_count} file{'' if file_count == 1 else 's'}"
                f"/{human_readable_size(archive_to_extract.stat().st_size)}]\n",
                total=total_bytes,
                **TQDM_MULTI_FILES_OPTIONS,
            )
        )

        # extract archive
        async def _decompressed_bytes(byte_progress: NonNegativeInt) -> None:
            if tqdm_progress.update(byte_progress) and log_cb:
                with log_catch(_logger, reraise=False):
                    await log_cb(f"{tqdm_progress}")
            await sub_prog.update(byte_progress)

        options = " ".join(
            [
                "x",  # extract
                "-bsp1",  # used for parsing progress
                "-y",  # reply yes to all
            ]
        )
        await _run_cli_command(
            f"{_7ZIP_EXECUTABLE} {options} {shlex.quote(f'{archive_to_extract}')} -o{shlex.quote(f'{destination_folder}')}",
            output_handler=_7ZipProgressParser(_decompressed_bytes).parse_chunk,
        )

    return {destination_folder / x for x in file_names_in_archive}
