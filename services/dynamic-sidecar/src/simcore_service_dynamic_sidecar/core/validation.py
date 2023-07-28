import json
import logging
import os
import re
from collections.abc import Generator
from typing import Any

import yaml
from servicelib.docker_constants import (
    DEFAULT_USER_SERVICES_NETWORK_NAME,
    SUFFIX_EGRESS_PROXY_NAME,
)

from ..modules.mounted_fs import MountedVolumes
from .docker_compose_utils import docker_compose_config
from .settings import ApplicationSettings

TEMPLATE_SEARCH_PATTERN = r"%%(.*?)%%"

_logger = logging.getLogger(__name__)


class InvalidComposeSpecError(Exception):
    """Exception used to signal incorrect docker-compose configuration file"""


def _assemble_container_name(
    settings: ApplicationSettings,
    service_key: str,
    user_given_container_name: str,
    index: int,
) -> str:
    strings_to_use = [
        settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE,
        str(index),
        user_given_container_name,
        service_key,
    ]

    return "-".join([x for x in strings_to_use if len(x) > 0])[
        : settings.DYNAMIC_SIDECAR_MAX_COMBINED_CONTAINER_NAME_LENGTH
    ].replace("_", "-")


def _get_forwarded_env_vars(container_key: str) -> list[str]:
    """returns env vars targeted to each container in the compose spec"""
    results = [
        # some services expect it, using it as empty
        "SIMCORE_NODE_BASEPATH=",
    ]
    for key in os.environ:
        if key.startswith("FORWARD_ENV_"):
            new_entry_key = key.replace("FORWARD_ENV_", "")

            # parsing `VAR={"destination_containers": ["destination_container"], "env_var": "PAYLOAD"}`
            new_entry_payload = json.loads(os.environ[key])
            if container_key not in new_entry_payload["destination_containers"]:
                continue

            new_entry_value = new_entry_payload["env_var"]
            new_entry = f"{new_entry_key}={new_entry_value}"
            results.append(new_entry)
    return results


def _extract_templated_entries(text: str) -> list[str]:
    return re.findall(TEMPLATE_SEARCH_PATTERN, text)


def _apply_templating_directives(
    stringified_compose_spec: str,
    services: dict[str, Any],
    spec_services_to_container_name: dict[str, str],
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
    compose_spec_env_vars: list[str], settings_env_vars: list[str]
) -> list[str]:
    def _gen_parts_env_vars(
        env_vars: list[str],
    ) -> Generator[tuple[str, str], None, None]:
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


def _connect_user_services(
    parsed_compose_spec: dict[str, Any], *, allow_internet_access: bool
) -> None:
    """
    Put all containers in the compose spec in the same network.
    The network name must only be unique inside the user defined spec.
    `docker-compose` will add some prefix to it.
    """
    networks = parsed_compose_spec.get("networks", None)
    if networks is None:
        parsed_compose_spec["networks"] = {}
    networks = parsed_compose_spec["networks"]

    networks[DEFAULT_USER_SERVICES_NETWORK_NAME] = {
        "internal": not allow_internet_access,
    }

    for service_name, service_content in parsed_compose_spec["services"].items():
        # do not add egress proxies to the backend network
        if SUFFIX_EGRESS_PROXY_NAME in service_name:
            continue

        service_networks = service_content.setdefault("networks", [])
        if service_networks is None:
            # if network is set without entries
            service_content["networks"] = {DEFAULT_USER_SERVICES_NETWORK_NAME: None}
        elif isinstance(service_networks, list):
            service_networks.append(DEFAULT_USER_SERVICES_NETWORK_NAME)
        else:
            # if the network is set as a dictionary (rather non official but works)

            # if the network already exists do not add (this is the case of the egress proxies)
            if DEFAULT_USER_SERVICES_NETWORK_NAME in service_networks:
                continue
            service_networks[DEFAULT_USER_SERVICES_NETWORK_NAME] = None


def parse_compose_spec(compose_file_content: str) -> Any:
    try:
        return yaml.safe_load(compose_file_content)
    except yaml.YAMLError as e:
        msg = f"{e}\n{compose_file_content}\nProvided yaml is not valid!"
        raise InvalidComposeSpecError(msg) from e


async def validate_compose_spec(
    settings: ApplicationSettings,
    compose_file_content: str,
    mounted_volumes: MountedVolumes,
) -> str:
    """
    Validates what looks like a docker compose spec and injects
    additional data to mainly make sure:
    - no collisions occur between container names
    - containers are located on the same docker network
    - properly target environment variables formwarded via
        settings on the service

    Finally runs docker-compose config to properly validate the result
    """
    _logger.debug("validating compose spec:\n%s", f"{compose_file_content=}")
    parsed_compose_spec = parse_compose_spec(compose_file_content)

    if parsed_compose_spec is None or not isinstance(parsed_compose_spec, dict):
        msg = f"{compose_file_content}\nProvided yaml is not valid!"
        raise InvalidComposeSpecError(msg)

    if not {"version", "services"}.issubset(set(parsed_compose_spec.keys())):
        msg = f"{compose_file_content}\nProvided yaml is not valid!"
        raise InvalidComposeSpecError(msg)

    version = parsed_compose_spec["version"]
    if version.startswith("1"):
        msg = f"Provided spec version '{version}' is not supported"
        raise InvalidComposeSpecError(msg)

    spec_services_to_container_name: dict[str, str] = {}

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

        # FIXME: tmp to comply with
        #  https://github.com/linuxserver/docker-baseimage-ubuntu/blob/bionic/root/etc/cont-init.d/10-adduser
        service_content["environment"].append(f"PUID={os.getuid()}")
        service_content["environment"].append(f"PGID={os.getgid()}")

        # inject paths to be mounted
        service_volumes = service_content.get("volumes", [])

        service_volumes.append(
            await mounted_volumes.get_inputs_docker_volume(settings.DY_SIDECAR_RUN_ID)
        )
        service_volumes.append(
            await mounted_volumes.get_outputs_docker_volume(settings.DY_SIDECAR_RUN_ID)
        )
        async for (
            state_paths_docker_volume
        ) in mounted_volumes.iter_state_paths_to_docker_volumes(
            settings.DY_SIDECAR_RUN_ID
        ):
            service_volumes.append(state_paths_docker_volume)

        service_content["volumes"] = service_volumes

    _connect_user_services(
        parsed_compose_spec,
        allow_internet_access=settings.DY_SIDECAR_USER_SERVICES_HAVE_INTERNET_ACCESS,
    )

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

    # validate against docker-compose config
    result = await docker_compose_config(compose_spec)

    if not result.success:
        _logger.warning(
            "'docker-compose config' failed for:\n%s\n%s",
            f"{compose_spec}",
            result.message,
        )
        msg = f"Invalid compose-specs:\n{result.message}"
        raise InvalidComposeSpecError(msg)

    return compose_spec
