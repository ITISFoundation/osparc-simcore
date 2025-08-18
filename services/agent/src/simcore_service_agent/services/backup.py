import asyncio
import logging
import os
import tempfile
from asyncio.streams import StreamReader
from datetime import timedelta
from pathlib import Path
from textwrap import dedent
from typing import Final
from uuid import uuid4

from fastapi import FastAPI
from servicelib.container_utils import run_command_in_container
from settings_library.utils_r_clone import resolve_provider

from ..core.settings import ApplicationSettings
from ..models.volumes import DynamicServiceVolumeLabels, VolumeDetails

_TIMEOUT_PERMISSION_CHANGES: Final[timedelta] = timedelta(minutes=5)

_logger = logging.getLogger(__name__)


_R_CLONE_CONFIG: Final[
    str
] = """
[dst]
type = s3
provider = {destination_provider}
access_key_id = {destination_access_key}
secret_access_key = {destination_secret_key}
endpoint = {destination_endpoint}
region = {destination_region}
acl = private
"""


def _get_config_file_path(settings: ApplicationSettings) -> Path:
    config_content = _R_CLONE_CONFIG.format(
        destination_provider=resolve_provider(
            settings.AGENT_VOLUMES_CLEANUP_S3_PROVIDER
        ),
        destination_access_key=settings.AGENT_VOLUMES_CLEANUP_S3_ACCESS_KEY,
        destination_secret_key=settings.AGENT_VOLUMES_CLEANUP_S3_SECRET_KEY,
        destination_endpoint=settings.AGENT_VOLUMES_CLEANUP_S3_ENDPOINT,
        destination_region=settings.AGENT_VOLUMES_CLEANUP_S3_REGION,
    )
    conf_path = Path(tempfile.gettempdir()) / f"rclone_config_{uuid4()}.ini"
    conf_path.write_text(config_content)
    return conf_path


def _get_s3_path(s3_bucket: str, labels: DynamicServiceVolumeLabels) -> Path:
    return (
        Path(s3_bucket)
        / labels.swarm_stack_name
        / f"{labels.study_id}"
        / f"{labels.node_uuid}"
        / labels.run_id
        / labels.directory_name
    )


async def _read_stream(stream: StreamReader) -> str:
    output = ""
    while line := await stream.readline():
        message = line.decode()
        output += message
        _logger.debug(message.strip("\n"))
    return output


def _get_r_clone_str_command(command: list[str], exclude_files: list[str]) -> str:
    # add files to be ignored
    for to_exclude in exclude_files:
        command.append("--exclude")
        command.append(to_exclude)

    str_command = " ".join(command)
    _logger.info(str_command)
    return str_command


def _log_expected_operation(
    labels: DynamicServiceVolumeLabels,
    s3_path: Path,
    r_clone_ls_output: str,
    volume_name: str,
) -> None:
    """
    This message will be logged as warning if any files will be synced
    """
    log_level = logging.INFO if r_clone_ls_output.strip() == "" else logging.WARNING

    formatted_message = dedent(
        f"""
        ---
        Volume data
        ---
        volume_name         {volume_name}
        destination_path    {s3_path}
        study_id:           {labels.study_id}
        node_id:            {labels.node_uuid}
        user_id:            {labels.user_id}
        run_id:             {labels.run_id}
        ---
        Files to sync by rclone
        ---\n{r_clone_ls_output.rstrip()}
        ---
    """
    )
    _logger.log(log_level, formatted_message)


async def _ensure_permissions_on_source_dir(source_dir: Path) -> None:
    self_container = os.environ["HOSTNAME"]
    await run_command_in_container(
        self_container,
        command=f"chmod -R o+rX '{source_dir}'",
        timeout=_TIMEOUT_PERMISSION_CHANGES.total_seconds(),
    )


async def _store_in_s3(
    settings: ApplicationSettings, volume_name: str, volume_details: VolumeDetails
) -> None:
    exclude_files = settings.AGENT_VOLUMES_CLEANUP_EXCLUDE_FILES

    config_file_path = _get_config_file_path(settings)

    source_dir = volume_details.mountpoint
    if not Path(source_dir).exists():
        _logger.info(
            "Volume mountpoint %s does not exist. Skipping backup, volume %s will be removed.",
            source_dir,
            volume_name,
        )
        return

    s3_path = _get_s3_path(
        settings.AGENT_VOLUMES_CLEANUP_S3_BUCKET, volume_details.labels
    )

    # listing files rclone will sync
    r_clone_ls = [
        "rclone",
        "--config",
        f"{config_file_path}",
        "ls",
        f"{source_dir}",
    ]
    process = await asyncio.create_subprocess_shell(
        _get_r_clone_str_command(r_clone_ls, exclude_files),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    assert process.stdout  # nosec
    r_clone_ls_output = await _read_stream(process.stdout)
    await process.wait()
    _log_expected_operation(
        volume_details.labels, s3_path, r_clone_ls_output, volume_name
    )

    await _ensure_permissions_on_source_dir(source_dir)

    # sync files via rclone
    r_clone_sync = [
        "rclone",
        "--config",
        f"{config_file_path}",
        "--low-level-retries",
        "3",
        "--retries",
        f"{settings.AGENT_VOLUMES_CLEANUP_RETRIES}",
        "--transfers",
        f"{settings.AGENT_VOLUMES_CLEANUP_PARALLELISM}",
        # below two options reduce to a minimum the memory footprint
        # https://forum.rclone.org/t/how-to-set-a-memory-limit/10230/4
        "--buffer-size",  # docs https://rclone.org/docs/#buffer-size-size
        "0M",
        "--stats",
        "5s",
        "--stats-one-line",
        "sync",
        f"{source_dir}",
        f"dst:{s3_path}",
        "--verbose",
    ]

    str_r_clone_sync = _get_r_clone_str_command(r_clone_sync, exclude_files)
    process = await asyncio.create_subprocess_shell(
        str_r_clone_sync,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    assert process.stdout  # nosec
    r_clone_sync_output = await _read_stream(process.stdout)
    await process.wait()
    _logger.info("Sync result:\n%s", r_clone_sync_output)

    if process.returncode != 0:
        msg = (
            f"Shell subprocesses yielded nonzero error code {process.returncode} "
            f"for command {str_r_clone_sync}\n{r_clone_sync_output}"
        )
        raise RuntimeError(msg)


async def backup_volume(
    app: FastAPI, volume_details: VolumeDetails, volume_name: str
) -> None:
    settings: ApplicationSettings = app.state.settings
    await _store_in_s3(
        settings=settings, volume_name=volume_name, volume_details=volume_details
    )
