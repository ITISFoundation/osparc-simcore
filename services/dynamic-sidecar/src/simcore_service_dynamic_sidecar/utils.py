import asyncio
import json
import logging
import os
import re
import tempfile
import traceback
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Generator, List, Tuple

import aiofiles
import yaml
from async_generator import asynccontextmanager
from async_timeout import timeout

from .settings import DynamicSidecarSettings

TEMPLATE_SEARCH_PATTERN = r"%%(.*?)%%"

logger = logging.getLogger(__name__)


class InvalidComposeSpec(Exception):
    """Exception used to signal incorrect docker-compose configuration file"""


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


async def async_command(command: str, command_timeout: float) -> Tuple[bool, str]:
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


def _assemble_container_name(
    settings: DynamicSidecarSettings,
    service_key: str,
    user_given_container_name: str,
    index: int,
) -> str:
    strings_to_use = [
        settings.compose_namespace,
        str(index),
        user_given_container_name,
        service_key,
    ]

    container_name = "-".join([x for x in strings_to_use if len(x) > 0])[
        : settings.max_combined_container_name_length
    ]
    return container_name.replace("_", "-")


def _get_forwarded_env_vars(container_key: str) -> List[str]:
    """retruns env vars targeted to each container in the compose spec"""
    results = [
        # some services expect it, using it as empty
        "SIMCORE_NODE_BASEPATH=",
    ]
    for key in os.environ.keys():
        if key.startswith("FORWARD_ENV_"):
            new_entry_key = key.replace("FORWARD_ENV_", "")

            # parsing `VAR={"destination_container": "destination_container", "env_var": "PAYLOAD"}`
            new_entry_payload = json.loads(os.environ[key])
            if new_entry_payload["destination_container"] != container_key:
                continue

            new_entry_value = new_entry_payload["env_var"]
            new_entry = f"{new_entry_key}={new_entry_value}"
            results.append(new_entry)
    return results


def _extract_templated_entries(text: str) -> List[str]:
    return re.findall(TEMPLATE_SEARCH_PATTERN, text)


def _apply_templating_directives(
    stringified_compose_spec: str,
    services: Dict[str, Any],
    spec_services_to_container_name: Dict[str, str],
) -> str:
    """
    Some custom rules are supported for replacing `container_name`
    with the following syntax `%%container_name.SERVICE_KEY_NAME%%`,
    where `SERVICE_KEY_NAME` targets a container in the compose spec

    If the directive cannot be applied it will just be left untouched
    """
    matches = set(_extract_templated_entries(stringified_compose_spec))
    for match in matches:
        parts = match.split(".")

        if len(parts) != 2:
            continue  # templating will be skipped

        target_property = parts[0]
        services_key = parts[1]
        if target_property != "container_name":
            continue  # also ignore if the container_name is not the directive to replace

        remapped_service_key = spec_services_to_container_name[services_key]
        replace_with = services.get(remapped_service_key, {}).get(
            "container_name", None
        )
        if replace_with is None:
            continue  # also skip here if nothing was found

        match_pattern = f"%%{match}%%"
        stringified_compose_spec = stringified_compose_spec.replace(
            match_pattern, replace_with
        )

    return stringified_compose_spec


def _merge_env_vars(
    compose_spec_env_vars: List[str], settings_env_vars: List[str]
) -> List[str]:
    def _gen_parts_env_vars(
        env_vars: List[str],
    ) -> Generator[Tuple[str, str], None, None]:
        for env_var in env_vars:
            key, value = env_var.split("=")
            yield key, value

    # pylint: disable=unnecessary-comprehension
    dict_spec_env_vars = {k: v for k, v in _gen_parts_env_vars(compose_spec_env_vars)}
    dict_settings_env_vars = {k: v for k, v in _gen_parts_env_vars(settings_env_vars)}

    # overwrite spec vars with vars from settings
    for key, value in dict_settings_env_vars.items():
        dict_spec_env_vars[key] = value

    # returns a single list of vars
    return [f"{k}={v}" for k, v in dict_spec_env_vars.items()]


def _inject_backend_networking(
    parsed_compose_spec: Dict[str, Any], network_name: str = "__backend__"
) -> None:
    """
    Put all containers in the compose spec in the same network.
    The `network_name` must only be unique inside the user defined spec;
    docker-compose will add some prefix to it.
    """

    networks = parsed_compose_spec.get("networks", {})
    networks[network_name] = None

    for service_content in parsed_compose_spec["services"].values():
        service_networks = service_content.get("networks", [])
        service_networks.append(network_name)
        service_content["networks"] = service_networks

    parsed_compose_spec["networks"] = networks


def validate_compose_spec(
    settings: DynamicSidecarSettings, compose_file_content: str
) -> str:
    """
    Validates what looks like a docker compose spec and injects 
    additional data to mainly make sure:
    - no collisions occur between container names
    - containers are located on the same docker network
    - properly target environment variables formwarded via 
        settings on the service
    """

    try:
        parsed_compose_spec = yaml.safe_load(compose_file_content)
    except yaml.YAMLError as e:
        raise InvalidComposeSpec(
            f"{str(e)}\n{compose_file_content}\nProvided yaml is not valid!"
        ) from e

    if parsed_compose_spec is None or not isinstance(parsed_compose_spec, dict):
        raise InvalidComposeSpec(f"{compose_file_content}\nProvided yaml is not valid!")

    if not {"version", "services"}.issubset(set(parsed_compose_spec.keys())):
        raise InvalidComposeSpec(f"{compose_file_content}\nProvided yaml is not valid!")

    version = parsed_compose_spec["version"]
    if version.startswith("1"):
        raise InvalidComposeSpec(f"Provided spec version '{version}' is not supported")

    spec_services_to_container_name: Dict[str, str] = {}

    spec_services = parsed_compose_spec["services"]
    for index, service in enumerate(spec_services):
        service_content = spec_services[service]

        # assemble and inject the container name
        user_given_container_name = service_content.get("container_name", "")
        container_name = _assemble_container_name(
            settings, service, user_given_container_name, index
        )
        service_content["container_name"] = container_name
        spec_services_to_container_name[service] = container_name

        # inject forwarded environment variables
        environment_entries = service_content.get("environment", [])
        service_settings_env_vars = _get_forwarded_env_vars(service)
        service_content["environment"] = _merge_env_vars(
            compose_spec_env_vars=environment_entries,
            settings_env_vars=service_settings_env_vars,
        )

    # if more then one container is defined, add an "backend" network
    if len(spec_services) > 1:
        _inject_backend_networking(parsed_compose_spec)

    # replace service_key with the container_name int the dict
    for service_key in list(spec_services.keys()):
        container_name_service_key = spec_services_to_container_name[service_key]
        service_data = spec_services.pop(service_key)

        depends_on = service_data.get("depends_on", None)
        if depends_on is not None:
            service_data["depends_on"] = [
                # replaces with the container name
                # if not found it leaves the old value
                spec_services_to_container_name.get(x, x)
                for x in depends_on
            ]

        spec_services[container_name_service_key] = service_data

    # transform back to string and return
    validated_compose_file_content = yaml.safe_dump(parsed_compose_spec)

    compose_spec = _apply_templating_directives(
        stringified_compose_spec=validated_compose_file_content,
        services=spec_services,
        spec_services_to_container_name=spec_services_to_container_name,
    )

    return compose_spec


def assemble_container_names(validated_compose_content: str) -> List[str]:
    """returns the list of container names from a validated compose_spec"""
    parsed_compose_spec = yaml.safe_load(validated_compose_content)
    return [
        service_data["container_name"]
        for service_data in parsed_compose_spec["services"].values()
    ]
