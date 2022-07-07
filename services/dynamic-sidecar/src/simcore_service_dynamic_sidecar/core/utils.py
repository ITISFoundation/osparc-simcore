import asyncio
import base64
import json
import logging
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, NamedTuple, Optional

import aiofiles
import httpx
import yaml
from aiofiles import os as aiofiles_os
from settings_library.docker_registry import RegistrySettings
from starlette import status
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from ..modules.mounted_fs import MountedVolumes

TEMPLATE_SEARCH_PATTERN = r"%%(.*?)%%"

HIDDEN_FILE_NAME = ".hidden_do_not_remove"

logger = logging.getLogger(__name__)


class CommandResult(NamedTuple):
    success: bool
    decoded_stdout: str
    command: str


class _RegistryNotReachableException(Exception):
    pass


@retry(
    wait=wait_fixed(1),
    stop=stop_after_delay(10),
    before_sleep=before_sleep_log(logger, logging.INFO),
    reraise=True,
)
async def _is_registry_reachable(registry_settings: RegistrySettings) -> None:
    async with httpx.AsyncClient() as client:
        params = {}
        if registry_settings.REGISTRY_AUTH:
            params["auth"] = (
                registry_settings.REGISTRY_USER,
                registry_settings.REGISTRY_PW.get_secret_value(),
            )

        protocol = "https" if registry_settings.REGISTRY_SSL else "http"
        url = f"{protocol}://{registry_settings.api_url}/"

        logging.info("Registry test url ='%s'", url)
        response = await client.get(url, **params)
        reachable = response.status_code == status.HTTP_200_OK and response.json() == {}
        if not reachable:
            logger.error("Response: %s", response)
            error_message = (
                f"Could not reach registry {registry_settings.api_url} "
                f"auth={registry_settings.REGISTRY_AUTH}"
            )
            raise _RegistryNotReachableException(error_message)


async def login_registry(registry_settings: RegistrySettings) -> None:
    """
    Creates ~/.docker/config.json and adds docker registry credentials
    """
    await _is_registry_reachable(registry_settings)

    def create_docker_config_file(registry_settings: RegistrySettings) -> None:
        user = registry_settings.REGISTRY_USER
        password = registry_settings.REGISTRY_PW.get_secret_value()
        docker_config = {
            "auths": {
                f"{registry_settings.resolved_registry_url}": {
                    "auth": base64.b64encode(f"{user}:{password}".encode()).decode(
                        "utf-8"
                    )
                }
            }
        }
        conf_file = Path.home() / ".docker" / "config.json"
        conf_file.parent.mkdir(exist_ok=True, parents=True)
        conf_file.write_text(json.dumps(docker_config))

    if registry_settings.REGISTRY_AUTH:
        await asyncio.get_event_loop().run_in_executor(
            None, create_docker_config_file, registry_settings
        )


@asynccontextmanager
async def write_to_tmp_file(file_contents: str) -> AsyncGenerator[Path, None]:
    """Disposes of file on exit"""
    # pylint: disable=protected-access,stop-iteration-return
    file_path = Path("/") / f"tmp/{next(tempfile._get_candidate_names())}"  # type: ignore
    async with aiofiles.open(file_path, mode="w") as tmp_file:
        await tmp_file.write(file_contents)
    try:
        yield file_path
    finally:
        await aiofiles_os.remove(file_path)


async def async_command(
    command: str, command_timeout: Optional[float] = None
) -> CommandResult:
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=command_timeout)

    except asyncio.TimeoutError:
        logger.warning(
            "%s timed out after %ss",
            f"{command=!r}",
            f"{command_timeout=}",
            stack_info=True,
        )
        raise

    return CommandResult(
        success=proc.returncode == 0,
        decoded_stdout=stdout.decode(),
        command=f"{command}",
    )


def assemble_container_names(validated_compose_content: str) -> list[str]:
    """returns the list of container names from a validated compose_spec"""
    parsed_compose_spec = yaml.safe_load(validated_compose_content)
    return [
        service_data["container_name"]
        for service_data in parsed_compose_spec["services"].values()
    ]


async def volumes_fix_permissions(mounted_volumes: MountedVolumes) -> None:
    # NOTE: by creating a hidden file on all mounted volumes
    # the same permissions are ensured and avoids
    # issues when starting the services
    for volume_path in mounted_volumes.all_disk_paths():
        hidden_file = volume_path / HIDDEN_FILE_NAME
        hidden_file.write_text(
            f"Directory must not be empty.\nCreated by {__file__}.\n"
            "Required by oSPARC internals to properly enforce permissions on this "
            "directory and all its files"
        )
