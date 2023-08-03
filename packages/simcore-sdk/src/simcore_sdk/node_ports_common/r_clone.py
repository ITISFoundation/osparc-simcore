import asyncio
import logging
import re
import shlex
from asyncio.streams import StreamReader
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final

from aiocache import cached
from aiofiles import tempfile
from pydantic import AnyUrl
from pydantic.errors import PydanticErrorMixin
from servicelib.progress_bar import ProgressBarData
from servicelib.utils import logged_gather
from settings_library.r_clone import RCloneSettings
from settings_library.utils_r_clone import get_r_clone_config

from .r_clone_utils import BaseRCloneLogParser, DebugLogParser, SyncProgressLogParser

S3_RETRIES: Final[int] = 3
S3_PARALLELISM: Final[int] = 5

_S3_CONFIG_KEY_DESTINATION: Final[str] = "s3-destination"
_S3_CONFIG_KEY_SOURCE: Final[str] = "s3-source"

_logger = logging.getLogger(__name__)


class BaseRCloneError(PydanticErrorMixin, RuntimeError):
    ...


class RCloneFailedError(BaseRCloneError):
    msg_template: str = (
        "Command {command} finished with exit code={returncode}:\n{stdout}\n{stderr}"
    )


class RCloneDirectoryNotFoundError(BaseRCloneError):
    msg_template: str = (
        "Provided path '{local_directory_path}' is a file. Expects a directory!"
    )


@asynccontextmanager
async def _config_file(config: str) -> AsyncIterator[str]:
    async with tempfile.NamedTemporaryFile("w") as f:
        await f.write(config)
        await f.flush()
        assert isinstance(f.name, str)  # nosec
        yield f.name


async def _read_stream(
    stream: StreamReader, r_clone_log_parsers: list[BaseRCloneLogParser]
):
    while True:
        line: bytes = await stream.readline()
        if line:
            decoded_line = line.decode()
            await logged_gather(
                *[parser(decoded_line) for parser in r_clone_log_parsers]
            )
        else:
            break


async def _async_r_clone_command(
    *cmd: str,
    r_clone_log_parsers: list[BaseRCloneLogParser] | None = None,
    cwd: str | None = None,
) -> str:
    str_cmd = " ".join(cmd)
    proc = await asyncio.create_subprocess_shell(
        str_cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd,
    )

    if r_clone_log_parsers:
        assert proc.stdout  # nosec
        await asyncio.wait([_read_stream(proc.stdout, r_clone_log_parsers)])

    stdout, stderr = await proc.communicate()
    decoded_stdout = stdout.decode()
    if proc.returncode != 0:
        raise RCloneFailedError(
            command=str_cmd,
            stdout=decoded_stdout,
            stderr=stderr,
            returncode=proc.returncode,
        )

    _logger.debug("'%s' result:\n%s", str_cmd, decoded_stdout)
    return decoded_stdout


@cached()
async def is_r_clone_available(r_clone_settings: RCloneSettings | None) -> bool:
    """returns: True if the `rclone` cli is installed and a configuration is provided"""
    if r_clone_settings is None:
        return False
    try:
        await _async_r_clone_command("rclone", "--version")
        return True
    except RCloneFailedError:
        return False


def _get_exclude_filters(exclude_patterns: set[str] | None) -> list[str]:
    if exclude_patterns is None:
        return []

    exclude_options: list[str] = []
    for entry in exclude_patterns:
        exclude_options.append("--exclude")
        # NOTE: in rclone ** is the equivalent of * in unix
        # for details about rclone filters https://rclone.org/filtering/
        exclude_options.append(entry.replace("*", "**"))

    return exclude_options


async def _sync_sources(
    r_clone_settings: RCloneSettings,
    progress_bar: ProgressBarData,
    *,
    source: str,
    destination: str,
    local_dir: Path,
    s3_config_key: str,
    exclude_patterns: set[str] | None,
    s3_retries: int = S3_RETRIES,
    s3_parallelism: int = S3_PARALLELISM,
    debug_logs: bool,
) -> None:
    r_clone_config_file_content = get_r_clone_config(
        r_clone_settings, s3_config_key=s3_config_key
    )
    async with _config_file(r_clone_config_file_content) as config_file_name:
        r_clone_command = (
            "rclone",
            "--config",
            config_file_name,
            "--retries",
            f"{s3_retries}",
            "--transfers",
            f"{s3_parallelism}",
            # below two options reduce to a minimum the memory footprint
            # https://forum.rclone.org/t/how-to-set-a-memory-limit/10230/4
            "--use-mmap",  # docs https://rclone.org/docs/#use-mmap
            "--buffer-size",  # docs https://rclone.org/docs/#buffer-size-size
            "0M",
            # make sure stats can be noticed
            "--stats-log-level",
            "NOTICE",
            # frequent polling for faster progress updates
            "--stats",
            "0.5s",
            "sync",
            shlex.quote(source),
            shlex.quote(destination),
            # filter options
            *_get_exclude_filters(exclude_patterns),
            "--progress",
            "--copy-links",
            "--verbose",
        )

        async with progress_bar.sub_progress(steps=100) as sub_progress:
            r_clone_log_parsers: list[BaseRCloneLogParser] = (
                [DebugLogParser()] if debug_logs else []
            )
            r_clone_log_parsers.append(SyncProgressLogParser(sub_progress))

            await _async_r_clone_command(
                *r_clone_command,
                r_clone_log_parsers=r_clone_log_parsers,
                cwd=f"{local_dir}",
            )


def _raise_if_directory_is_file(local_directory_path: Path) -> None:
    if local_directory_path.exists() and local_directory_path.is_file():
        raise RCloneDirectoryNotFoundError(local_directory_path=local_directory_path)


async def sync_local_to_s3(
    r_clone_settings: RCloneSettings,
    progress_bar: ProgressBarData,
    *,
    local_directory_path: Path,
    upload_s3_link: AnyUrl,
    exclude_patterns: set[str] | None = None,
    debug_logs: bool = False,
) -> None:
    """transfer the contents of a local directory to an s3 path

    :raises e: RCloneFailedError
    """
    _raise_if_directory_is_file(local_directory_path)

    upload_s3_path = re.sub(r"^s3://", "", upload_s3_link)
    _logger.debug(" %s; %s", f"{upload_s3_link=}", f"{upload_s3_path=}")

    await _sync_sources(
        r_clone_settings,
        progress_bar,
        source=f"{local_directory_path}",
        destination=f"{_S3_CONFIG_KEY_DESTINATION}:{upload_s3_path}",
        local_dir=local_directory_path,
        s3_config_key=_S3_CONFIG_KEY_DESTINATION,
        exclude_patterns=exclude_patterns,
        debug_logs=debug_logs,
    )


async def sync_s3_to_local(
    r_clone_settings: RCloneSettings,
    progress_bar: ProgressBarData,
    *,
    local_directory_path: Path,
    download_s3_link: AnyUrl,
    exclude_patterns: set[str] | None = None,
    debug_logs: bool = False,
) -> None:
    """transfer the contents of a path in s3 to a local directory

    :raises e: RCloneFailedError
    """
    _raise_if_directory_is_file(local_directory_path)

    download_s3_path = re.sub(r"^s3://", "", download_s3_link)
    _logger.debug(" %s; %s", f"{download_s3_link=}", f"{download_s3_path=}")

    await _sync_sources(
        r_clone_settings,
        progress_bar,
        source=f"{_S3_CONFIG_KEY_SOURCE}:{download_s3_path}",
        destination=f"{local_directory_path}",
        local_dir=local_directory_path,
        s3_config_key=_S3_CONFIG_KEY_SOURCE,
        exclude_patterns=exclude_patterns,
        debug_logs=debug_logs,
    )
