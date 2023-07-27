import asyncio
import base64
import json
import logging
import os
import signal
import tempfile
import time
from asyncio.subprocess import Process
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import NamedTuple

import aiofiles
import httpx
import psutil
import yaml
from aiofiles import os as aiofiles_os
from servicelib.error_codes import create_error_code
from settings_library.docker_registry import RegistrySettings
from starlette import status
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from ..modules.mounted_fs import MountedVolumes

HIDDEN_FILE_NAME = ".hidden_do_not_remove"

logger = logging.getLogger(__name__)


class CommandResult(NamedTuple):
    success: bool
    message: str
    command: str
    elapsed: float | None


class _RegistryNotReachableError(Exception):
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
            raise _RegistryNotReachableError(error_message)


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
async def write_to_tmp_file(file_contents: str) -> AsyncIterator[Path]:
    """Disposes of file on exit"""
    file_path = Path(tempfile.mkdtemp()) / "file"
    async with aiofiles.open(file_path, mode="w") as tmp_file:
        await tmp_file.write(file_contents)
    try:
        yield file_path
    finally:
        await aiofiles_os.remove(file_path)


def _close_transport(proc: Process):
    # Closes transport (initialized during 'await proc.communicate(...)' ) and avoids error:
    #
    # Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7f871d0c7e50>
    # Traceback (most recent call last):
    #   File " ... .pyenv/versions/3.9.12/lib/python3.9/asyncio/base_subprocess.py", line 126, in __del__
    #     self.close()
    #

    # SEE implementation of asyncio.subprocess.Process._read_stream(...)
    for fd in (1, 2):
        # pylint: disable=protected-access
        if transport := getattr(proc, "_transport", None):  # noqa: SIM102
            if t := transport.get_pipe_transport(fd):
                t.close()


async def async_command(command: str, timeout: float | None = None) -> CommandResult:
    """
    Does not raise Exception
    """
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        # NOTE that stdout/stderr together. Might want to separate them?
    )
    start = time.time()

    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)

    except asyncio.TimeoutError:
        proc.terminate()
        _close_transport(proc)

        # The SIGTERM signal is a generic signal used to cause program termination.
        # Unlike SIGKILL, this signal can be **blocked, handled, and ignored**.
        # It is the normal way to politely ask a program to terminate, i.e. giving
        # the opportunity to the underying process to perform graceful shutdown
        # (i.e. run shutdown events and cleanup tasks)
        #
        # SEE https://www.gnu.org/software/libc/manual/html_node/Termination-Signals.html
        #
        # There is a chance that the launched process ignores SIGTERM
        # in that case, it would proc.wait() forever. This code will be
        # used only to run docker-compose CLI which behaves well. Nonetheless,
        # we add here some asserts.
        assert await proc.wait() == -signal.SIGTERM  # nosec
        assert not psutil.pid_exists(proc.pid)  # nosec

        logger.warning(
            "Process %s timed out after %ss",
            f"{command=!r}",
            f"{timeout=}",
        )
        return CommandResult(
            success=False,
            message=f"Execution timed out after {timeout} secs",
            command=f"{command}",
            elapsed=time.time() - start,
        )

    except Exception as err:  # pylint: disable=broad-except
        error_code = create_error_code(err)
        logger.exception(
            "Process with %s failed unexpectedly [%s]",
            f"{command=!r}",
            f"{error_code}",
            extra={"error_code": error_code},
        )

        return CommandResult(
            success=False,
            message=f"Unexpected error [{error_code}]",
            command=f"{command}",
            elapsed=time.time() - start,
        )

    # no exceptions
    return CommandResult(
        success=proc.returncode == os.EX_OK,
        message=stdout.decode(),
        command=f"{command}",
        elapsed=time.time() - start,
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
    for volume_path in mounted_volumes.all_disk_paths_iter():
        hidden_file = volume_path / HIDDEN_FILE_NAME
        hidden_file.write_text(
            f"Directory must not be empty.\nCreated by {__file__}.\n"
            "Required by oSPARC internals to properly enforce permissions on this "
            "directory and all its files"
        )
