import asyncio
import logging
import os
import shlex
from asyncio.streams import StreamReader
from pathlib import Path

from aiocache import cached
from pydantic import AnyUrl, ByteSize
from pydantic.errors import PydanticErrorMixin
from servicelib.progress_bar import ProgressBarData
from servicelib.utils import logged_gather
from settings_library.aws_s3_cli import AwsS3CliSettings
from settings_library.r_clone import S3Provider

from .aws_s3_cli_utils import SyncAwsCliS3ProgressLogParser
from .r_clone import DebugLogParser
from .r_clone_utils import BaseLogParser, CommandResultCaptureParser

_logger = logging.getLogger(__name__)


_CONVERT_SYMLINK_TO_OSPARC_LINK = "rclonelink"  # We call it `rclonelink` to maintain backward compatibility with rclone


class BaseAwsS3CliError(PydanticErrorMixin, RuntimeError):
    ...


class AwsS3CliFailedError(BaseAwsS3CliError):
    msg_template: str = (
        "Command {command} finished with exit code={returncode}:\n{command_output}"
    )


class AwsS3CliDirectoryNotFoundError(BaseAwsS3CliError):
    msg_template: str = (
        "Provided path '{local_directory_path}' is a file. Expects a directory!"
    )


async def _read_stream(
    stream: StreamReader, aws_s3_cli_log_parsers: list[BaseLogParser]
):
    while True:
        line: bytes = await stream.readline()
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
        },
    )

    command_result_parser = CommandResultCaptureParser()
    aws_cli_s3_log_parsers = (
        [*aws_cli_s3_log_parsers, command_result_parser]
        if aws_cli_s3_log_parsers
        else [command_result_parser]
    )

    assert proc.stdout  # nosec
    await asyncio.wait([_read_stream(proc.stdout, [*aws_cli_s3_log_parsers])])

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

    if aws_s3_cli_settings.AWS_S3_CLI_PROVIDER.value != S3Provider.AWS:
        cli_command.insert(
            1, f"--endpoint-url {aws_s3_cli_settings.AWS_S3_CLI_S3.S3_ENDPOINT}"
        )

    result = await _async_aws_cli_command(
        *cli_command, aws_s3_cli_settings=aws_s3_cli_settings
    )
    return ByteSize(result.strip())


def _get_size_and_manage_symlink(path: Path) -> ByteSize:
    if path.is_symlink():
        # Convert symlink to a .osparclink file that can be stored in the S3
        target_path = os.readlink(path)
        _name = path.name + f".{_CONVERT_SYMLINK_TO_OSPARC_LINK}"

        textfile_path = path.parent / _name
        with open(textfile_path, "w") as file:
            file.write(target_path)
        return ByteSize(0)
    return ByteSize(path.stat().st_size)


async def _get_local_folder_size(local_path: Path) -> ByteSize:
    total_size = 0
    for dirpath, _, filenames in os.walk(local_path):
        for filename in filenames:
            file_path = Path(dirpath) / filename
            total_size += _get_size_and_manage_symlink(Path(file_path))
    return ByteSize(total_size)


async def _sync_sources(
    aws_s3_cli_settings: AwsS3CliSettings,
    progress_bar: ProgressBarData,
    *,
    source: str,
    destination: str,
    local_dir: Path,
    exclude_patterns: set[str] | None,
    debug_logs: bool = True,
) -> None:

    if source.startswith("s3://"):
        folder_size: ByteSize = await _get_s3_folder_size(
            aws_s3_cli_settings, s3_path=shlex.quote(source)
        )
    else:
        folder_size = await _get_local_folder_size(Path(source))

    cli_command = [
        "aws",
        "s3",
        "sync",
        "--delete",
        shlex.quote(source),  # <-- source
        shlex.quote(destination),  # <-- destination
        # filter options
        *_get_exclude_filters(exclude_patterns),
        "--no-follow-symlinks",
    ]

    if not aws_s3_cli_settings.AWS_S3_CLI_PROVIDER.value == S3Provider.AWS:
        cli_command.insert(
            1, f"--endpoint-url {aws_s3_cli_settings.AWS_S3_CLI_S3.S3_ENDPOINT}"
        )

    async with progress_bar.sub_progress(
        steps=folder_size,
        progress_unit="Byte",
        description=f"transferring {local_dir.name}",
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
        raise AwsS3CliDirectoryNotFoundError(local_directory_path=local_directory_path)


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

    await _sync_sources(
        aws_s3_cli_settings,
        progress_bar,
        source=f"{local_directory_path}",
        destination=f"{upload_s3_path}",
        local_dir=local_directory_path,
        exclude_patterns=exclude_patterns,
        debug_logs=debug_logs,
    )

    # Remove the temporary created .osparclink files after they were uploaded to S3
    for textfile_path in local_directory_path.rglob(
        f"*.{_CONVERT_SYMLINK_TO_OSPARC_LINK}"
    ):
        textfile_path.unlink()


def textfile_to_symlink(textfile_path: Path, symlink_path: Path):
    with open(textfile_path) as file:
        target_path = file.read().strip()
    os.symlink(target_path, symlink_path)


def convert_osparclink_to_symlink(textfile_path: Path):
    symlink_path = textfile_path.with_suffix("")
    textfile_to_symlink(textfile_path, symlink_path)
    textfile_path.unlink()


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

    await _sync_sources(
        aws_s3_cli_settings,
        progress_bar,
        source=f"{download_s3_path}",
        destination=f"{local_directory_path}",
        local_dir=local_directory_path,
        exclude_patterns=exclude_patterns,
        debug_logs=debug_logs,
    )

    # Convert .osparclink files to real symlink files after they were downloaded from S3
    for textfile_path in local_directory_path.rglob(
        f"*.{_CONVERT_SYMLINK_TO_OSPARC_LINK}"
    ):
        convert_osparclink_to_symlink(textfile_path)
