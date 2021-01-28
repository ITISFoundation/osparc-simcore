import asyncio
import logging
import tempfile
from contextlib import asynccontextmanager
from typing import List, Tuple

import aiofiles
import yaml
from async_timeout import timeout

from .settings import ServiceSidecarSettings

logger = logging.getLogger(__name__)


class InvalidComposeSpec(Exception):
    """Exception used to signal incorrect docker-compose configuration file"""


@asynccontextmanager
async def write_to_tmp_file(file_contents):
    """Disposes of file on exit"""
    # pylint: disable=protected-access,stop-iteration-return
    file_path = "/tmp/" + next(tempfile._get_candidate_names())
    async with aiofiles.open(file_path, mode="w") as tmp_file:
        await tmp_file.write(file_contents)
    try:
        yield file_path
    finally:
        # TODO: put this back when done with the PR
        # await aiofiles.os.remove(file_path)
        pass


async def async_command(command, command_timeout: float) -> Tuple[bool, str]:
    """Returns if the command exited correctly and the stdout of the command """
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
        message = f"Timed out after {command_timeout} seconds while running {command}"
        logger.warning(message)
        return False, message

    decoded_stdout = stdout.decode()
    finished_without_errors = proc.returncode == 0

    return finished_without_errors, decoded_stdout


def _assemble_container_name(
    settings: ServiceSidecarSettings,
    service_key: str,
    user_given_container_name: str,
    index: int,
) -> str:
    container_name = f"{settings.compose_namespace}_{index}_{user_given_container_name}_{service_key}"[
        : settings.max_combined_container_name_length
    ]
    return container_name


def validate_compose_spec(
    settings: ServiceSidecarSettings, compose_file_content: str
) -> str:
    """
    Checks the following:
    - proper yaml format
    - no "container_name" service property allowed, because it can
        spawn 2 cotainers with the same name
    """

    try:
        parsed_compose_spec = yaml.safe_load(compose_file_content)
    except yaml.YAMLError as e:
        raise InvalidComposeSpec(f"{str(e)}\nProvided yaml is not valid!") from e

    for index, service in enumerate(parsed_compose_spec["services"]):
        service_content = parsed_compose_spec["services"][service]
        user_given_container_name = service_content.get("container_name", "")
        # assemble and inject the container name
        service_content["container_name"] = _assemble_container_name(
            settings, service, user_given_container_name, index
        )

    # transform back to string and return
    validated_compose_file_content = yaml.safe_dump(parsed_compose_spec)
    return validated_compose_file_content


def assemble_container_names(validated_compose_content: str) -> List[str]:
    """returns the list of container names from a validated compose_spec"""
    parsed_compose_spec = yaml.safe_load(validated_compose_content)
    return [
        service_data["container_name"]
        for service_data in parsed_compose_spec["services"].values()
    ]
