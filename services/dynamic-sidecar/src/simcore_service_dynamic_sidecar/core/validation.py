import logging
import os
import re
from collections.abc import Generator
from typing import Any, Final, NamedTuple

import yaml
from common_library.json_serialization import json_loads
from servicelib.docker_constants import (
    DEFAULT_USER_SERVICES_NETWORK_NAME,
    SUFFIX_EGRESS_PROXY_NAME,
)

from ..modules.mounted_fs import MountedVolumes
from ..modules.user_services_tracing import (
    OTEL_COLLECTOR_SERVICE_NAME,
    UserServicesTracingSettings,
    build_otel_collector_compose_service,
    build_otel_resource_attributes,
)
from ._extra_container_resources import (
    compute_extra_containers_footprint,
    deduct_extra_containers_resources,
)
from .docker_compose_utils import docker_compose_config
from .settings import ApplicationSettings

TEMPLATE_SEARCH_PATTERN = r"%%(.*?)%%"

_TEMPLATE_DIRECTIVE_NUM_PARTS: Final[int] = 2

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
            new_entry_payload = json_loads(os.environ[key])
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

        if len(parts) != _TEMPLATE_DIRECTIVE_NUM_PARTS:
            continue  # templating will be skipped

        target_property = parts[0]
        services_key = parts[1]
        if target_property != "container_name":
            continue  # also ignore if the container_name is not the directive to replace

        remapped_service_key = spec_services_to_container_name[services_key]
        replace_with = services.get(remapped_service_key, {}).get("container_name", None)
        if replace_with is None:
            continue  # also skip here if nothing was found

        match_pattern = f"%%{match}%%"
        stringified_compose_spec = stringified_compose_spec.replace(match_pattern, replace_with)

    return stringified_compose_spec


def _merge_env_vars(
    compose_spec_env_vars: list[str] | dict[str, str],
    settings_env_vars: list[str] | dict[str, str],
) -> list[str]:
    def _gen_parts_env_vars(
        env_vars: list[str] | dict[str, str],
    ) -> Generator[tuple[str, str]]:
        assert isinstance(env_vars, list | dict)  # nosec

        if isinstance(env_vars, list):
            for env_var in env_vars:
                key, value = env_var.split("=")
                yield key, value
        else:
            yield from env_vars.items()

    # pylint: disable=unnecessary-comprehension
    dict_spec_env_vars = dict(_gen_parts_env_vars(compose_spec_env_vars))
    dict_settings_env_vars = dict(_gen_parts_env_vars(settings_env_vars))

    # overwrite spec vars with vars from settings
    for key, value in dict_settings_env_vars.items():
        dict_spec_env_vars[key] = value  # noqa: PERF403

    # returns a single list of vars
    return [f"{k}={v}" for k, v in dict_spec_env_vars.items()]


def _connect_user_services_to_shared_network(
    parsed_compose_spec: dict[str, Any], *, allow_internet_access: bool
) -> None:
    """
    Put all containers in the compose spec in the same network.
    The network name must only be unique inside the user defined spec.
    `docker compose` will add some prefix to it.
    """
    networks = parsed_compose_spec.get("networks")
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
        result = yaml.safe_load(compose_file_content)

        if result is None or not isinstance(result, dict):
            msg = f"{compose_file_content}\nProvided yaml is not valid!"
            raise InvalidComposeSpecError(msg)

        if "services" not in set(result.keys()):
            msg = f"{compose_file_content}\nProvided yaml is not valid!"
            raise InvalidComposeSpecError(msg)

        return result
    except yaml.YAMLError as e:
        msg = f"{e}\n{compose_file_content}\nProvided yaml is not valid!"
        raise InvalidComposeSpecError(msg) from e


class ComposeSpecValidation(NamedTuple):
    compose_spec: str
    current_container_names: list[str]
    original_to_current_container_names: dict[str, str]


def _assign_container_names(
    settings: ApplicationSettings,
    spec_services: dict[str, Any],
) -> dict[str, str]:
    spec_services_to_container_name: dict[str, str] = {}
    for index, service in enumerate(spec_services):
        service_content = spec_services[service]
        user_given_container_name = service_content.get("container_name", "")
        container_name = _assemble_container_name(settings, service, user_given_container_name, index)
        service_content["container_name"] = container_name
        spec_services_to_container_name[service] = container_name
    return spec_services_to_container_name


def _inject_forwarded_env_vars(spec_services: dict[str, Any]) -> None:
    for service, service_content in spec_services.items():
        environment_entries = service_content.get("environment", [])
        service_settings_env_vars = _get_forwarded_env_vars(service)
        service_content["environment"] = _merge_env_vars(
            compose_spec_env_vars=environment_entries,
            settings_env_vars=service_settings_env_vars,
        )
        # LinuxServer.io base images use PUID/PGID to create a user with the host's UID/GID
        # SEE https://github.com/linuxserver/docker-baseimage-ubuntu/blob/noble/root/etc/s6-overlay/s6-rc.d/init-adduser/run
        service_content["environment"].append(f"PUID={os.getuid()}")
        service_content["environment"].append(f"PGID={os.getgid()}")


async def _mount_shared_volumes(
    settings: ApplicationSettings,
    spec_services: dict[str, Any],
    mounted_volumes: MountedVolumes,
) -> None:
    for service_content in spec_services.values():
        service_volumes = service_content.get("volumes", [])
        service_volumes.append(await mounted_volumes.get_inputs_docker_volume(settings.DY_SIDECAR_RUN_ID))
        service_volumes.append(await mounted_volumes.get_outputs_docker_volume(settings.DY_SIDECAR_RUN_ID))
        async for state_paths_docker_volume in mounted_volumes.iter_state_paths_to_docker_volumes(
            settings.DY_SIDECAR_RUN_ID
        ):
            service_volumes.append(state_paths_docker_volume)
        if settings.DY_SIDECAR_USER_PREFERENCES_PATH is not None and (
            user_preferences_volume := await mounted_volumes.get_user_preferences_path_volume(
                settings.DY_SIDECAR_RUN_ID
            )
        ):
            service_volumes.append(user_preferences_volume)
        service_content["volumes"] = service_volumes


def _inject_otel_collector(
    parsed_compose_spec: dict[str, Any],
    settings: ApplicationSettings,
    user_services_tracing_settings: UserServicesTracingSettings,
    traces_volume_mount: str,
    user_service_names: list[str],
    collector_container_name: str,
) -> None:
    parsed_compose_spec["services"][OTEL_COLLECTOR_SERVICE_NAME] = build_otel_collector_compose_service(
        user_services_tracing_settings,
        settings,
        collector_container_name,
        traces_volume_mount,
    )

    # Make user services depend on the collector so docker stops them FIRST
    # giving the collector time to receive final spans, before it gets SIGTERM.
    for svc_name in user_service_names:
        svc_data = parsed_compose_spec["services"][svc_name]
        depends_on = svc_data.get("depends_on", [])
        if isinstance(depends_on, dict):
            depends_on = list(depends_on)
        depends_on.append(OTEL_COLLECTOR_SERVICE_NAME)
        svc_data["depends_on"] = depends_on


async def _inject_tracing(
    parsed_compose_spec: dict[str, Any],
    settings: ApplicationSettings,
    mounted_volumes: MountedVolumes,
    spec_services_to_container_name: dict[str, str],
) -> None:
    user_services_tracing_settings = settings.DYNAMIC_SIDECAR_USER_SERVICES_TRACING_CONFIG
    spec_services = parsed_compose_spec["services"]
    user_service_keys = list(spec_services.keys())

    collector_container_name = _assemble_container_name(
        settings,
        OTEL_COLLECTOR_SERVICE_NAME,
        OTEL_COLLECTOR_SERVICE_NAME,
        len(spec_services),
    )

    traces_volume_mount = await mounted_volumes.get_traces_docker_volume(settings.DY_SIDECAR_RUN_ID)
    _inject_otel_collector(
        parsed_compose_spec,
        settings,
        user_services_tracing_settings,
        traces_volume_mount,
        user_service_keys,
        collector_container_name,
    )

    resource_attributes = build_otel_resource_attributes(settings)
    for service_key in user_service_keys:
        service_env = spec_services[service_key].get("environment", [])
        service_env.extend(
            [
                f"OTEL_EXPORTER_OTLP_ENDPOINT=http://{collector_container_name}:4318",
                f"OTEL_SERVICE_NAME={spec_services_to_container_name[service_key]}",
                f"OTEL_RESOURCE_ATTRIBUTES={resource_attributes}",
            ]
        )

    spec_services_to_container_name[OTEL_COLLECTOR_SERVICE_NAME] = collector_container_name


def _remap_service_keys(
    spec_services: dict[str, Any],
    spec_services_to_container_name: dict[str, str],
) -> None:
    """Replaces service keys with container names in the services dict (in-place)."""
    for service_key in list(spec_services.keys()):
        container_name_service_key = spec_services_to_container_name[service_key]
        service_data = spec_services.pop(service_key)

        depends_on = service_data.get("depends_on", None)
        if depends_on is not None:
            service_data["depends_on"] = [spec_services_to_container_name.get(x, x) for x in depends_on]

        spec_services[container_name_service_key] = service_data


async def get_and_validate_compose_spec(
    settings: ApplicationSettings,
    compose_file_content: str,
    mounted_volumes: MountedVolumes,
    *,
    is_user_services_tracing_enabled: bool,
) -> ComposeSpecValidation:
    _logger.debug("validating compose spec:\n%s", f"{compose_file_content=}")
    parsed_compose_spec = parse_compose_spec(compose_file_content)

    spec_services = parsed_compose_spec["services"]

    spec_services_to_container_name = _assign_container_names(settings, spec_services)
    _inject_forwarded_env_vars(spec_services)
    await _mount_shared_volumes(settings, spec_services, mounted_volumes)

    if is_user_services_tracing_enabled:
        await _inject_tracing(
            parsed_compose_spec,
            settings,
            mounted_volumes,
            spec_services_to_container_name,
        )

    _connect_user_services_to_shared_network(
        parsed_compose_spec,
        allow_internet_access=settings.DY_SIDECAR_USER_SERVICES_HAVE_INTERNET_ACCESS,
    )

    # deduct helper-containers resource footprints from the biggest user service AFTER:
    extra = compute_extra_containers_footprint(
        settings,
        egress_proxy_count=sum(1 for name in spec_services if SUFFIX_EGRESS_PROXY_NAME in name),
        with_tracing=is_user_services_tracing_enabled,
        with_rclone=settings.DY_SIDECAR_REQUIRES_DATA_MOUNTING,
    )
    deduct_extra_containers_resources(parsed_compose_spec, extra=extra, settings=settings)

    _remap_service_keys(spec_services, spec_services_to_container_name)

    compose_spec = _apply_templating_directives(
        stringified_compose_spec=yaml.safe_dump(parsed_compose_spec),
        services=spec_services,
        spec_services_to_container_name=spec_services_to_container_name,
    )
    result = await docker_compose_config(compose_spec)

    if not result.success:
        _logger.warning(
            "'docker compose config' failed for:\n%s\n%s",
            f"{compose_spec}",
            result.message,
        )
        msg = f"Invalid compose-specs:\n{result.message}"
        raise InvalidComposeSpecError(msg)

    current_container_names = list(spec_services_to_container_name.values())

    return ComposeSpecValidation(
        compose_spec=compose_spec,
        current_container_names=current_container_names,
        original_to_current_container_names=dict(spec_services_to_container_name),
    )
