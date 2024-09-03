import asyncio
import contextlib
import logging
import os
import shlex
from asyncio.streams import StreamReader
from pathlib import Path

from aiocache import cached  # type: ignore[import-untyped]
from models_library.basic_types import IDStr
from pydantic import AnyUrl, ByteSize
from pydantic.errors import PydanticErrorMixin
from servicelib.progress_bar import ProgressBarData
from servicelib.utils import logged_gather
from settings_library.aws_s3_cli import AwsS3CliSettings

from ._utils import BaseLogParser
from .aws_s3_cli_utils import SyncAwsCliS3ProgressLogParser
from .r_clone_utils import CommandResultCaptureParser, DebugLogParser

_logger = logging.getLogger(__name__)


_OSPARC_SYMLINK_EXTENSION = ".rclonelink"  # named `rclonelink` to maintain backwards


class BaseAwsS3CliError(PydanticErrorMixin, RuntimeError):
    ...


class AwsS3CliFailedError(BaseAwsS3CliError):
    msg_template: str = (
        "Command {command} finished with exit code={returncode}:\n{command_output}"
    )


class AwsS3CliPathIsAFileError(BaseAwsS3CliError):
    msg_template: str = (
        "Provided path '{local_directory_path}' is a file. Expects a directory!"
    )


class CRLFStreamReaderWrapper:
    """
    A wrapper for asyncio streams that converts carriage return characters to newlines.

    When the AWS S3 CLI provides progress updates, it uses carriage return ('\r') characters
    to overwrite the output. This wrapper converts '\r' to '\n' to standardize line endings,
    allowing the stream to be read line by line using newlines as delimiters.
    """

    def __init__(self, reader):
        self.reader = reader
        self.buffer = bytearray()

    async def readline(self):
        while True:
            # Check if there's a newline character in the buffer
            if b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                return line + b"\n"
            # Read a chunk of data from the stream
            chunk = await self.reader.read(1024)
            if not chunk:
                # If no more data is available, return the buffer as the final line
                line = self.buffer
                self.buffer = bytearray()
                return line
            # Replace \r with \n in the chunk
            chunk = chunk.replace(b"\r", b"\n")
            self.buffer.extend(chunk)


async def _read_stream(
    stream: StreamReader, aws_s3_cli_log_parsers: list[BaseLogParser]
):
    reader_wrapper = CRLFStreamReaderWrapper(stream)
    while True:
        line: bytes = await reader_wrapper.readline()
        if line:
            decoded_line = line.decode()
            await logged_gather(
                *[parser(decoded_line) for parser in aws_s3_cli_log_parsers]
            )
        else:
            break


@cached()
async def is_aws_s3_cli_available(aws_s3_cli_settings: AwsS3CliSettings | None) -> bool:
    """returns: True if the `aws` cli is installed and a configuration is provided"""
    if aws_s3_cli_settings is None:
        return False
    try:
        await _async_aws_cli_command(
            "aws", "--version", aws_s3_cli_settings=aws_s3_cli_settings
        )
        return True
    except AwsS3CliFailedError:
        return False


async def _async_aws_cli_command(
    *cmd: str,
    aws_s3_cli_settings: AwsS3CliSettings,
    aws_cli_s3_log_parsers: list[BaseLogParser] | None = None,
) -> str:
    str_cmd = " ".join(cmd)
    proc = await asyncio.create_subprocess_shell(
        str_cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env={
            "AWS_ACCESS_KEY_ID": aws_s3_cli_settings.AWS_S3_CLI_S3.S3_ACCESS_KEY,
            "AWS_SECRET_ACCESS_KEY": aws_s3_cli_settings.AWS_S3_CLI_S3.S3_SECRET_KEY,
            "AWS_REGION": aws_s3_cli_settings.AWS_S3_CLI_S3.S3_REGION,
        },
    )

    command_result_parser = CommandResultCaptureParser()
    aws_cli_s3_log_parsers = (
        [*aws_cli_s3_log_parsers, command_result_parser]
        if aws_cli_s3_log_parsers
        else [command_result_parser]
    )

    assert proc.stdout  # nosec
    await asyncio.wait(
        [asyncio.create_task(_read_stream(proc.stdout, [*aws_cli_s3_log_parsers]))]
    )

    _stdout, _stderr = await proc.communicate()

    command_output = command_result_parser.get_output()
    if proc.returncode != 0:
        raise AwsS3CliFailedError(
            command=str_cmd,
            command_output=command_output,
            returncode=proc.returncode,
        )

    _logger.debug("'%s' result:\n%s", str_cmd, command_output)
    return command_output


def _get_exclude_filters(exclude_patterns: set[str] | None) -> list[str]:
    if exclude_patterns is None:
        return []

    exclude_options: list[str] = []
    for entry in exclude_patterns:
        exclude_options.append("--exclude")
        exclude_options.append(entry.replace("*", "**"))

    return exclude_options


async def _get_s3_folder_size(
    aws_s3_cli_settings: AwsS3CliSettings,
    *,
    s3_path: str,
) -> ByteSize:
    cli_command = [
        "aws",
        "s3",
        "ls",
        "--summarize",
        "--recursive",
        s3_path,
        "| grep 'Total Size' | awk '{print $3}'",
    ]

    if aws_s3_cli_settings.AWS_S3_CLI_S3.S3_ENDPOINT:
        cli_command.insert(
            1, f"--endpoint-url {aws_s3_cli_settings.AWS_S3_CLI_S3.S3_ENDPOINT}"
        )

    result = await _async_aws_cli_command(
        *cli_command, aws_s3_cli_settings=aws_s3_cli_settings
    )
    return ByteSize(result.strip())


def _get_file_size_and_manage_symlink(path: Path) -> ByteSize:
    if path.is_symlink():
        # Convert symlink to a .rclonelink file that can be stored in the S3
        target_path = f"{path.readlink()}"
        _name = path.name + _OSPARC_SYMLINK_EXTENSION

        textfile_path = path.parent / _name
        textfile_path.write_text(target_path)
        return ByteSize(textfile_path.stat().st_size)
    return ByteSize(path.stat().st_size)


async def _get_local_folder_size_and_manage_symlink(local_path: Path) -> ByteSize:
    total_size = 0
    for dirpath, _, filenames in os.walk(local_path):
        for filename in filenames:
            file_path = Path(dirpath) / filename
            total_size += _get_file_size_and_manage_symlink(Path(file_path))
    return ByteSize(total_size)


async def _sync_sources(
    aws_s3_cli_settings: AwsS3CliSettings,
    progress_bar: ProgressBarData,
    *,
    source: str,
    destination: str,
    local_dir: Path,
    exclude_patterns: set[str] | None,
    debug_logs: bool,
) -> None:

    if source.startswith("s3://"):
        folder_size: ByteSize = await _get_s3_folder_size(
            aws_s3_cli_settings, s3_path=shlex.quote(source)
        )
    else:
        folder_size = await _get_local_folder_size_and_manage_symlink(Path(source))

    cli_command = [
        "aws",
        "s3",
        "sync",
        "--delete",
        shlex.quote(source),
        shlex.quote(destination),
        # filter options
        *_get_exclude_filters(exclude_patterns),
        "--no-follow-symlinks",
    ]

    if aws_s3_cli_settings.AWS_S3_CLI_S3.S3_ENDPOINT:
        cli_command.insert(
            1, f"--endpoint-url {aws_s3_cli_settings.AWS_S3_CLI_S3.S3_ENDPOINT}"
        )

    async with progress_bar.sub_progress(
        steps=folder_size,
        progress_unit="Byte",
        description=IDStr(f"transferring {local_dir.name}"),
    ) as sub_progress:
        aws_s3_cli_log_parsers: list[BaseLogParser] = (
            [DebugLogParser()] if debug_logs else []
        )
        aws_s3_cli_log_parsers.append(SyncAwsCliS3ProgressLogParser(sub_progress))

    await _async_aws_cli_command(
        *cli_command,
        aws_s3_cli_settings=aws_s3_cli_settings,
        aws_cli_s3_log_parsers=aws_s3_cli_log_parsers,
    )


def _raise_if_directory_is_file(local_directory_path: Path) -> None:
    if local_directory_path.exists() and local_directory_path.is_file():
        raise AwsS3CliPathIsAFileError(local_directory_path=local_directory_path)


@contextlib.asynccontextmanager
async def remove_local_osparclinks(local_directory_path):
    try:
        yield
    finally:
        # Remove the temporary created .rclonelink files generated by `_get_local_folder_size_and_manage_symlink`
        for textfile_path in local_directory_path.rglob(
            f"*{_OSPARC_SYMLINK_EXTENSION}"
        ):
            textfile_path.unlink()


@contextlib.asynccontextmanager
async def convert_osparclinks_to_original_symlinks(local_directory_path):
    try:
        yield
    finally:
        # Convert .rclonelink files to real symlink files after they were downloaded from S3
        for textfile_path in local_directory_path.rglob(
            f"*{_OSPARC_SYMLINK_EXTENSION}"
        ):
            symlink_path = textfile_path.with_suffix("")
            target_path = textfile_path.read_text().strip()
            os.symlink(target_path, symlink_path)
            textfile_path.unlink()


async def sync_local_to_s3(
    aws_s3_cli_settings: AwsS3CliSettings,
    progress_bar: ProgressBarData,
    *,
    local_directory_path: Path,
    upload_s3_link: AnyUrl,
    exclude_patterns: set[str] | None = None,
    debug_logs: bool = False,
) -> None:
    """transfer the contents of a local directory to an s3 path

    :raises e: AwsS3CliFailedError
    """
    _raise_if_directory_is_file(local_directory_path)

    upload_s3_path = upload_s3_link
    _logger.debug(" %s; %s", f"{upload_s3_link=}", f"{upload_s3_path=}")

    async with remove_local_osparclinks(local_directory_path):
        await _sync_sources(
            aws_s3_cli_settings,
            progress_bar,
            source=f"{local_directory_path}",
            destination=f"{upload_s3_path}",
            local_dir=local_directory_path,
            exclude_patterns=exclude_patterns,
            debug_logs=debug_logs,
        )


async def sync_s3_to_local(
    aws_s3_cli_settings: AwsS3CliSettings,
    progress_bar: ProgressBarData,
    *,
    local_directory_path: Path,
    download_s3_link: AnyUrl,
    exclude_patterns: set[str] | None = None,
    debug_logs: bool = False,
) -> None:
    """transfer the contents of a path in s3 to a local directory

    :raises e: AwsS3CliFailedError
    """
    _raise_if_directory_is_file(local_directory_path)

    download_s3_path = download_s3_link
    _logger.debug(" %s; %s", f"{download_s3_link=}", f"{download_s3_path=}")

    async with convert_osparclinks_to_original_symlinks(local_directory_path):
        await _sync_sources(
            aws_s3_cli_settings,
            progress_bar,
            source=f"{download_s3_path}",
            destination=f"{local_directory_path}",
            local_dir=local_directory_path,
            exclude_patterns=exclude_patterns,
            debug_logs=debug_logs,
        )
