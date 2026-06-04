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
from servicelib.tracing import SourceOrigin, create_standard_attributes

from ..modules.mounted_fs import MountedVolumes
from .docker_compose_utils import docker_compose_config
from .settings import ApplicationSettings, UserServiceTracingSettings

TEMPLATE_SEARCH_PATTERN = r"%%(.*?)%%"

_OTEL_COLLECTOR_SERVICE_NAME: Final[str] = "dy-otel-collector"
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


def _connect_user_services(parsed_compose_spec: dict[str, Any], *, allow_internet_access: bool) -> None:
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
        return yaml.safe_load(compose_file_content)
    except yaml.YAMLError as e:
        msg = f"{e}\n{compose_file_content}\nProvided yaml is not valid!"
        raise InvalidComposeSpecError(msg) from e


def _generate_otel_collector_config(
    tracing_settings: UserServiceTracingSettings,
    settings: ApplicationSettings,
) -> str:
    """Generates the OTEL Collector YAML config for the injected collector container."""

    # NOTE: added to collector container so they are always present
    attributes = create_standard_attributes(
        user_id=settings.DY_SIDECAR_USER_ID,
        project_id=settings.DY_SIDECAR_PROJECT_ID,
        node_id=settings.DY_SIDECAR_NODE_ID,
        product_name=settings.DY_SIDECAR_PRODUCT_NAME,
        run_id=settings.DY_SIDECAR_RUN_ID,
        source_origin=SourceOrigin.USER_SERVICE,
    )

    config = {
        "receivers": {
            "otlp": {
                "protocols": {
                    "http": {"endpoint": "0.0.0.0:4318"},
                }
            }
        },
        "processors": {
            "batch": {"timeout": "5s"},
            "resource": {"attributes": [{"key": k, "value": v, "action": "upsert"} for k, v in attributes.items()]},
        },
        "exporters": {
            "file": {
                "path": "/traces/spans.jsonl",
                "rotation": {
                    "max_megabytes": tracing_settings.USER_SERVICES_TRACING_COLLECTOR_MAX_FILE_SIZE_MB,
                    "max_backups": tracing_settings.USER_SERVICES_TRACING_COLLECTOR_MAX_BACKUPS,
                },
                "flush_interval": (
                    f"{int(tracing_settings.USER_SERVICES_TRACING_COLLECTOR_FLUSH_INTERVAL.total_seconds())}s"
                ),
            }
        },
        "service": {
            "pipelines": {
                "traces": {
                    "receivers": ["otlp"],
                    "processors": ["batch", "resource"],
                    "exporters": ["file"],
                }
            }
        },
    }
    return yaml.safe_dump(config, default_flow_style=False)


def _build_otel_resource_attributes(settings: ApplicationSettings) -> str:
    """Builds the OTEL_RESOURCE_ATTRIBUTES value with simcore.* prefixed keys."""
    # NOTE: added to each service via env var, user could in therory overwrite them,
    # but to do so they need to put in extra effor
    attrs = create_standard_attributes(
        service_key=settings.DY_SIDECAR_SERVICE_KEY,
        service_version=settings.DY_SIDECAR_SERVICE_VERSION,
        source_origin=None,
    )
    return ",".join(f"{k}={v}" for k, v in attrs.items() if v)


def _inject_otel_collector(
    parsed_compose_spec: dict[str, Any],
    settings: ApplicationSettings,
    tracing_settings: UserServiceTracingSettings,
    traces_volume_mount: str,
    user_service_names: list[str],
) -> str:
    """Injects the OTEL Collector service into the compose spec.

    Returns the collector's container name for use in OTEL_EXPORTER_OTLP_ENDPOINT.
    """
    collector_config_yaml = _generate_otel_collector_config(tracing_settings, settings)

    collector_container_name = _assemble_container_name(
        settings,
        _OTEL_COLLECTOR_SERVICE_NAME,
        _OTEL_COLLECTOR_SERVICE_NAME,
        len(parsed_compose_spec["services"]),
    )

    collector_service: dict[str, Any] = {
        "image": tracing_settings.USER_SERVICES_TRACING_COLLECTOR_IMAGE,
        "container_name": collector_container_name,
        "user": f"{os.getuid()}:{os.getgid()}",
        "command": ["--config=env:OTEL_COLLECTOR_CONFIG"],
        "environment": [
            f"OTEL_COLLECTOR_CONFIG={collector_config_yaml}",
        ],
        "volumes": [
            traces_volume_mount,
        ],
        "stop_grace_period": (
            f"{int(tracing_settings.USER_SERVICES_TRACING_COLLECTOR_STOP_GRACE_PERIOD.total_seconds())}s"
        ),
    }

    parsed_compose_spec["services"][_OTEL_COLLECTOR_SERVICE_NAME] = collector_service

    # Make user services depend on collector so Docker Compose stops them FIRST
    # (reverse dependency order), giving the collector time to receive final spans
    # before it gets SIGTERM.
    # NOTE: _remap_service_keys always flattens depends_on to a list (dropping
    # long-form conditions), so we normalise to list here unconditionally.
    for svc_name in user_service_names:
        svc_data = parsed_compose_spec["services"][svc_name]
        depends_on = svc_data.get("depends_on", [])
        if isinstance(depends_on, dict):
            depends_on = list(depends_on)
        depends_on.append(_OTEL_COLLECTOR_SERVICE_NAME)
        svc_data["depends_on"] = depends_on

    return collector_container_name


class ComposeSpecValidation(NamedTuple):
    compose_spec: str
    current_container_names: list[str]
    original_to_current_container_names: dict[str, str]


def _validate_compose_structure(parsed_compose_spec: Any, compose_file_content: str) -> None:
    """Validates basic structure of parsed compose spec."""
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


async def _process_service_entries(
    settings: ApplicationSettings,
    spec_services: dict[str, Any],
    mounted_volumes: MountedVolumes,
) -> dict[str, str]:
    """Processes each service: assigns container names, injects env vars and volumes.

    Returns a mapping from service key to assigned container name.
    """
    spec_services_to_container_name: dict[str, str] = {}

    for index, service in enumerate(spec_services):
        service_content = spec_services[service]

        # assemble and inject the container name
        user_given_container_name = service_content.get("container_name", "")
        container_name = _assemble_container_name(settings, service, user_given_container_name, index)
        service_content["container_name"] = container_name
        spec_services_to_container_name[service] = container_name

        # inject forwarded environment variables
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

        # inject paths to be mounted
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

    return spec_services_to_container_name


async def _inject_tracing(
    parsed_compose_spec: dict[str, Any],
    settings: ApplicationSettings,
    mounted_volumes: MountedVolumes,
    spec_services_to_container_name: dict[str, str],
) -> None:
    """Injects OTEL collector and env vars into user services when tracing is enabled."""
    tracing_settings = settings.DYNAMIC_SIDECAR_USER_SERVICES_TRACING
    spec_services = parsed_compose_spec["services"]

    traces_volume_mount = await mounted_volumes.get_traces_docker_volume(settings.DY_SIDECAR_RUN_ID)
    user_service_keys = list(spec_services.keys())

    collector_container_name = _inject_otel_collector(
        parsed_compose_spec,
        settings,
        tracing_settings,
        traces_volume_mount,
        user_service_keys,
    )

    # inject OTEL env vars into each user service
    resource_attributes = _build_otel_resource_attributes(settings)
    for service_key in user_service_keys:
        service_env = spec_services[service_key].get("environment", [])
        otel_env_vars = [
            f"OTEL_EXPORTER_OTLP_ENDPOINT=http://{collector_container_name}:4318",
            f"OTEL_SERVICE_NAME={spec_services_to_container_name[service_key]}",
            f"OTEL_RESOURCE_ATTRIBUTES={resource_attributes}",
        ]
        service_env.extend(otel_env_vars)

    # track the collector in container names
    spec_services_to_container_name[_OTEL_COLLECTOR_SERVICE_NAME] = collector_container_name


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
    """
    Validates what looks like a docker compose spec and injects
    additional data to mainly make sure:
    - no collisions occur between container names
    - containers are located on the same docker network
    - properly target environment variables formwarded via
        settings on the service

    Finally runs docker compose config to properly validate the result
    """
    _logger.debug("validating compose spec:\n%s", f"{compose_file_content=}")
    parsed_compose_spec = parse_compose_spec(compose_file_content)

    _validate_compose_structure(parsed_compose_spec, compose_file_content)

    spec_services = parsed_compose_spec["services"]

    # Phase 1: Process each service (container names, env vars, volumes)
    spec_services_to_container_name = await _process_service_entries(settings, spec_services, mounted_volumes)

    # Phase 2: Inject OTEL collector if tracing enabled
    if is_user_services_tracing_enabled:
        await _inject_tracing(parsed_compose_spec, settings, mounted_volumes, spec_services_to_container_name)

    # Phase 3: Connect all user services to the shared network
    _connect_user_services(
        parsed_compose_spec,
        allow_internet_access=settings.DY_SIDECAR_USER_SERVICES_HAVE_INTERNET_ACCESS,
    )

    # Phase 4: Remap service keys → container names
    _remap_service_keys(spec_services, spec_services_to_container_name)

    # Phase 5: Apply templating and validate with docker compose
    validated_compose_file_content = yaml.safe_dump(parsed_compose_spec)

    compose_spec = _apply_templating_directives(
        stringified_compose_spec=validated_compose_file_content,
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
