import asyncio
from contextlib import asynccontextmanager
from typing import Tuple
import tempfile

import aiofiles
import yaml


from sidecar import config


class InvalidComposeSpec(Exception):
    """Exception used to signal incorrect docker-compose configuration file"""


@asynccontextmanager
async def write_to_tmp_file(file_contents):
    """Disposes of file on exit"""
    file_path = tempfile.gettempdir()
    async with aiofiles.open(file_path, mode="w") as tmp_file:
        await tmp_file.write(file_contents)
    try:
        yield file_path
    finally:
        await aiofiles.os.remove(file_path)


async def async_command(command) -> Tuple[bool, str]:
    """Returns if the command exited correctly and the stdout of the command """
    proc = await asyncio.create_subprocess_shell(
        command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )

    stdout, _ = await proc.communicate()
    decoded_stdout = stdout.decode()
    finished_without_errors = proc.returncode == 0

    return finished_without_errors, decoded_stdout


def assemble_container_name(service_key):
    return f"{config.compose_namespace}_{service_key}_1"


def validate_compose_spec(compose_file_content: str) -> None:
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

    for service in parsed_compose_spec["services"]:
        service_content = parsed_compose_spec["services"][service]
        if "container_name" in service_content:
            raise InvalidComposeSpec(
                "Field 'container_name', found int service "
                f"'{service}', is not permitted"
            )

        container_name = assemble_container_name(service)
        container_name_length = len(container_name)
        if container_name_length > 255:
            raise InvalidComposeSpec(
                "The length of the final formatted container name "
                f"'{container_name}' is '{container_name_length}' "
                f"instead of '{config.max_combined_container_name_length}'"
            )
