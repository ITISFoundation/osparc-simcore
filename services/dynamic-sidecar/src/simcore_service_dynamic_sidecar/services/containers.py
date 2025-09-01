import logging
from asyncio import Lock
from typing import Any, Final

from aiodocker import DockerError
from common_library.errors_classes import OsparcErrorMixin
from common_library.json_serialization import json_loads
from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import ContainersComposeSpec
from models_library.api_schemas_dynamic_sidecar.containers import (
    ActivityInfo,
    ActivityInfoOrNone,
)
from pydantic import TypeAdapter, ValidationError
from servicelib.container_utils import (
    ContainerExecCommandFailedError,
    ContainerExecContainerNotFoundError,
    ContainerExecTimeoutError,
    run_command_in_container,
)

from ..core.docker_utils import docker_client
from ..core.settings import ApplicationSettings
from ..core.validation import (
    ComposeSpecValidation,
    get_and_validate_compose_spec,
    parse_compose_spec,
)
from ..models.shared_store import SharedStore
from ..modules.mounted_fs import MountedVolumes

_INACTIVE_FOR_LONG_TIME: Final[int] = 2**63 - 1

_logger = logging.getLogger(__name__)


async def create_compose_spec(
    app: FastAPI,
    *,
    containers_compose_spec: ContainersComposeSpec,
) -> None:
    settings: ApplicationSettings = app.state.settings
    shared_store: SharedStore = app.state.shared_store
    mounted_volumes: MountedVolumes = app.state.mounted_volumes

    async with shared_store:
        compose_spec_validation: ComposeSpecValidation = (
            await get_and_validate_compose_spec(
                settings=settings,
                compose_file_content=containers_compose_spec.docker_compose_yaml,
                mounted_volumes=mounted_volumes,
            )
        )
        shared_store.compose_spec = compose_spec_validation.compose_spec
        shared_store.container_names = compose_spec_validation.current_container_names
        shared_store.original_to_container_names = (
            compose_spec_validation.original_to_current_container_names
        )

    _logger.info("Validated compose-spec:\n%s", f"{shared_store.compose_spec}")

    assert shared_store.compose_spec


def _format_result(
    container_inspect: dict[str, Any], *, only_status: bool
) -> dict[str, Any]:
    if only_status:
        container_state = container_inspect.get("State", {})

        # pending is another fake state use to share more information with the frontend
        return {
            "Status": container_state.get("Status", "pending"),
            "Error": container_state.get("Error", ""),
        }

    return container_inspect


async def containers_docker_inspect(
    app: FastAPI, *, only_status: bool
) -> dict[str, Any]:
    container_restart_lock: Lock = app.state.container_restart_lock
    shared_store: SharedStore = app.state.shared_store

    async with container_restart_lock, docker_client() as docker:
        container_names = shared_store.container_names

        results = {}
        for container in container_names:
            container_instance = await docker.containers.get(container)
            container_inspect = await container_instance.show()
            results[container] = _format_result(
                container_inspect, only_status=only_status
            )

        return results


async def get_containers_activity(app: FastAPI) -> ActivityInfoOrNone:
    settings: ApplicationSettings = app.state.settings
    shared_store: SharedStore = app.state.shared_store

    inactivity_command = settings.DY_SIDECAR_CALLBACKS_MAPPING.inactivity
    if inactivity_command is None:
        return None

    container_name = inactivity_command.service

    try:
        inactivity_response = await run_command_in_container(
            shared_store.original_to_container_names[inactivity_command.service],
            command=inactivity_command.command,
            timeout=inactivity_command.timeout,
        )
    except (
        ContainerExecContainerNotFoundError,
        ContainerExecCommandFailedError,
        ContainerExecTimeoutError,
        DockerError,
    ):
        _logger.warning(
            "Could not run inactivity command '%s' in container '%s'",
            inactivity_command.command,
            container_name,
            exc_info=True,
        )
        return ActivityInfo(seconds_inactive=_INACTIVE_FOR_LONG_TIME)

    try:
        return TypeAdapter(ActivityInfo).validate_json(inactivity_response)
    except ValidationError:
        _logger.warning(
            "Could not parse command result '%s' as '%s'",
            inactivity_response,
            ActivityInfo.__name__,
            exc_info=True,
        )

    return ActivityInfo(seconds_inactive=_INACTIVE_FOR_LONG_TIME)


class BaseGetNameError(OsparcErrorMixin, RuntimeError):
    pass


class InvalidFilterFormatError(BaseGetNameError):
    msg_template: str = "Provided filters, could not parsed {filters}"


class MissingDockerComposeDownSpecError(BaseGetNameError):
    msg_template: str = "No spec for docker compose down was found"


class ContainerNotFoundError(BaseGetNameError):
    msg_template: str = (
        "No container found for network={network_name} and exclude={exclude}"
    )


async def get_containers_name(app: FastAPI, *, filters: str) -> str | dict[str, Any]:
    """
    Searches for the container's name given the network
    on which the proxy communicates with it.
    Supported filters:
        network: matches against the exact network name
            assigned to the container; `will include`
            containers
        exclude: matches if contained in the name of the
            container; `will exclude` containers
    """
    shared_store: SharedStore = app.state.shared_store

    filters_dict: dict[str, str] = json_loads(filters)
    if not isinstance(filters_dict, dict):
        raise InvalidFilterFormatError(filters=filters_dict)
    network_name: str | None = filters_dict.get("network")
    exclude: str | None = filters_dict.get("exclude")

    stored_compose_content = shared_store.compose_spec
    if stored_compose_content is None:
        raise MissingDockerComposeDownSpecError

    compose_spec = parse_compose_spec(stored_compose_content)

    container_name = None

    spec_services = compose_spec["services"]
    for service in spec_services:
        service_content = spec_services[service]
        if network_name in service_content.get("networks", {}):
            if exclude is not None and exclude in service_content["container_name"]:
                # removing this container from results
                continue
            container_name = service_content["container_name"]
            break

    if container_name is None:
        raise ContainerNotFoundError(network_name=network_name, exclude=exclude)

    return f"{container_name}"


class ContainerIsMissingError(OsparcErrorMixin, RuntimeError):
    msg_template: str = (
        "No container='{container_id}' was found in started_containers='{container_names}'"
    )


async def inspect_container(
    app: FastAPI,
    *,
    container_id: str,
) -> dict[str, Any]:
    """Returns information about the container, like docker inspect command"""
    shared_store: SharedStore = app.state.shared_store

    container_names = shared_store.container_names
    if container_id not in container_names:
        _logger.warning(
            "No container='%s' was found in started_containers='%s'",
            container_id,
            container_names,
        )
        raise ContainerIsMissingError(
            container_id=container_id, container_names=container_names
        )

    async with docker_client() as docker:
        container_instance = await docker.containers.get(container_id)
        inspect_result: dict[str, Any] = await container_instance.show()
        return inspect_result
