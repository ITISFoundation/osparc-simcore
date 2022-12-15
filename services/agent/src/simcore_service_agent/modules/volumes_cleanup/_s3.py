import asyncio
import logging
from asyncio.streams import StreamReader
from pathlib import Path
from textwrap import dedent
from typing import Final

from settings_library.r_clone import S3Provider
from settings_library.utils_r_clone import resolve_provider

logger = logging.getLogger(__name__)

R_CLONE_CONFIG = """
[dst]
type = s3
provider = {destination_provider}
access_key_id = {destination_access_key}
secret_access_key = {destination_secret_key}
endpoint = {destination_endpoint}
region = {destination_region}
acl = private
"""
VOLUME_NAME_FIXED_PORTION: Final[int] = 78


def get_config_file_path(
    s3_endpoint: str,
    s3_access_key: str,
    s3_secret_key: str,
    s3_region: str,
    s3_provider: S3Provider,
) -> Path:
    config_content = R_CLONE_CONFIG.format(
        destination_provider=resolve_provider(s3_provider),
        destination_access_key=s3_access_key,
        destination_secret_key=s3_secret_key,
        destination_endpoint=s3_endpoint,
        destination_region=s3_region,
    )
    conf_path = Path("/tmp/rclone_config.ini")  # NOSONAR
    conf_path.write_text(config_content)  # pylint:disable=unspecified-encoding
    return conf_path


def _get_dir_name(volume_name: str) -> str:
    # from: "dyv_a0430d06-40d2-4c92-9490-6aca30e00fc7_898fff63-d402-5566-a99b-091522dd2ae9_stuptuo_krow_nayvoj_emoh_"
    # gets: "home_jovyan_work_outputs"
    return volume_name[VOLUME_NAME_FIXED_PORTION:][::-1].strip("_")


def _get_s3_path(s3_bucket: str, labels: dict[str, str], volume_name: str) -> Path:

    joint_key = "/".join(
        (
            s3_bucket,
            labels["swarm_stack_name"],
            labels["study_id"],
            labels["node_uuid"],
            labels["run_id"],
            _get_dir_name(volume_name),
        )
    )
    return Path(f"/{joint_key}")


async def _read_stream(stream: StreamReader) -> str:
    output = ""
    while line := await stream.readline():
        message = line.decode()
        output += message
        logger.debug(message.strip("\n"))
    return output


def _get_r_clone_str_command(command: list[str], exclude_files: list[str]) -> str:
    # add files to be ignored
    for to_exclude in exclude_files:
        command.append("--exclude")
        command.append(to_exclude)

    str_command = " ".join(command)
    logger.info(str_command)
    return str_command


def _log_expected_operation(
    dyv_volume_labels: dict[str, str],
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
        study_id:           {dyv_volume_labels['study_id']}
        node_id:            {dyv_volume_labels['node_uuid']}
        user_id:            {dyv_volume_labels['user_id']}
        run_id:             {dyv_volume_labels['run_id']}
        ---
        Files to sync by rclone
        ---\n{r_clone_ls_output.rstrip()}
        ---
    """
    )
    logger.log(log_level, formatted_message)


async def store_to_s3(  # pylint:disable=too-many-locals,too-many-arguments
    volume_name: str,
    dyv_volume: dict,
    s3_endpoint: str,
    s3_access_key: str,
    s3_secret_key: str,
    s3_bucket: str,
    s3_region: str,
    s3_provider: S3Provider,
    s3_retries: int,
    s3_parallelism: int,
    exclude_files: list[str],
) -> None:
    config_file_path = get_config_file_path(
        s3_endpoint=s3_endpoint,
        s3_access_key=s3_access_key,
        s3_secret_key=s3_secret_key,
        s3_region=s3_region,
        s3_provider=s3_provider,
    )

    source_dir = dyv_volume["Mountpoint"]
    s3_path = _get_s3_path(s3_bucket, dyv_volume["Labels"], volume_name)

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

    r_clone_ls_output = await _read_stream(process.stdout)
    await process.wait()
    _log_expected_operation(
        dyv_volume["Labels"], s3_path, r_clone_ls_output, volume_name
    )

    # sync files via rclone
    r_clone_sync = [
        "rclone",
        "--config",
        f"{config_file_path}",
        "--low-level-retries",
        "3",
        "--retries",
        f"{s3_retries}",
        "--transfers",
        f"{s3_parallelism}",
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

    r_clone_sync_output = await _read_stream(process.stdout)
    await process.wait()
    logger.info("Sync result:\n%s", r_clone_sync_output)

    if process.returncode != 0:
        raise RuntimeError(
            f"Shell subprocesses yielded nonzero error code {process.returncode} "
            f"for command {str_r_clone_sync}\n{r_clone_sync_output}"
        )
