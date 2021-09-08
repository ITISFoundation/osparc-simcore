import asyncio
import base64
import json
import logging
import tempfile
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, List, Tuple

import aiodocker
import aiofiles
import yaml
from async_timeout import timeout
from fastapi import HTTPException
from settings_library.docker_registry import RegistrySettings

TEMPLATE_SEARCH_PATTERN = r"%%(.*?)%%"

logger = logging.getLogger(__name__)


async def login_registry(registry_settings: RegistrySettings) -> None:
    def create_docker_config_file(registry_settings: RegistrySettings) -> None:
        user = registry_settings.REGISTRY_USER
        password = registry_settings.REGISTRY_PW.get_secret_value()
        docker_config = {
            "auths": {
                f"{registry_settings.resolved_registry_url}": {
                    "auth": base64.b64encode(
                        f"{user}:{password}".encode("utf-8")
                    ).decode("utf-8")
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
        await aiofiles.os.remove(file_path)


@asynccontextmanager
async def docker_client() -> AsyncGenerator[aiodocker.Docker, None]:
    docker = aiodocker.Docker()
    try:
        yield docker
    except aiodocker.exceptions.DockerError as error:
        logger.exception("An unexpected Docker error occurred")
        raise HTTPException(error.status, detail=error.message) from error
    finally:
        await docker.close()


async def async_command(command: str, command_timeout: float) -> Tuple[bool, str]:
    """Returns if the command exited correctly and the stdout of the command"""
    proc = await asyncio.create_subprocess_shell(
        command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    # because the Processes returned by create_subprocess_shell it is not possible to
    # have a timeout otherwise nor to stream the response from the process.
    try:
        async with timeout(command_timeout):
            stdout, _ = await proc.communicate()
    except asyncio.TimeoutError:
        message = (
            f"{traceback.format_exc()}\nTimed out after {command_timeout} "
            f"seconds while running {command}"
        )
        logger.warning(message)
        return False, message

    decoded_stdout = stdout.decode()
    logger.info("'%s' result:\n%s", command, decoded_stdout)
    finished_without_errors = proc.returncode == 0

    return finished_without_errors, decoded_stdout


def assemble_container_names(validated_compose_content: str) -> List[str]:
    """returns the list of container names from a validated compose_spec"""
    parsed_compose_spec = yaml.safe_load(validated_compose_content)
    return [
        service_data["container_name"]
        for service_data in parsed_compose_spec["services"].values()
    ]
