import logging
import urllib.parse
from copy import deepcopy
from typing import Annotated, Any, Final, cast

import yaml
from fastapi import APIRouter, Depends, HTTPException, status
from models_library.docker import DockerGenericTag
from models_library.groups import GroupAtDB
from models_library.service_settings_labels import (
    ComposeSpecLabelDict,
    SimcoreServiceSettingLabelEntry,
)
from models_library.services import ServiceKey, ServiceVersion
from models_library.services_resources import (
    BootMode,
    ImageResources,
    ResourcesDict,
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from models_library.utils.docker_compose import replace_env_vars_in_compose_spec
from pydantic import TypeAdapter

from ..._constants import RESPONSE_MODEL_POLICY, SIMCORE_SERVICE_SETTINGS_LABELS
from ...db.repositories.services import ServicesRepository
from ...services.director import DirectorApi
from ...services.function_services import is_function_service
from ...utils.service_resources import (
    merge_service_resources_with_user_specs,
    parse_generic_resource,
)
from ..dependencies.database import get_repository
from ..dependencies.director import get_director_api
from ..dependencies.services import get_default_service_resources
from ..dependencies.user_groups import list_user_groups

router = APIRouter()
_logger = logging.getLogger(__name__)

SIMCORE_SERVICE_COMPOSE_SPEC_LABEL: Final[str] = "simcore.service.compose-spec"
_DEPRECATED_RESOURCES: Final[list[str]] = ["MPI"]
_BOOT_MODE_TO_RESOURCE_NAME_MAP: Final[dict[str, str]] = {"MPI": "MPI", "GPU": "VRAM"}


def _compute_service_available_boot_modes(
    settings: list[SimcoreServiceSettingLabelEntry],
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> list[BootMode]:
    """returns the service boot-modes.
    currently this uses the simcore.service.settings labels if available for backwards compatiblity.
    if MPI is found, then boot mode is set to MPI, if GPU is found then boot mode is set to GPU, else to CPU.
    In the future a dedicated label might be used, to add openMP for example. and to not abuse the resources of a service.
    Also these will be used in a project to allow the user to choose among different boot modes
    """

    resource_entries = filter(lambda entry: entry.name.lower() == "resources", settings)
    generic_resources: ResourcesDict = {}
    for entry in resource_entries:
        if not isinstance(entry.value, dict):
            _logger.warning(
                "resource %s for %s got invalid type",
                f"{entry.model_dump()!r}",
                f"{service_key}:{service_version}",
            )
            continue
        generic_resources |= parse_generic_resource(
            entry.value.get("Reservations", {}).get("GenericResources", []),
        )
    # currently these are unique boot modes
    for mode in BootMode:
        if (
            _BOOT_MODE_TO_RESOURCE_NAME_MAP.get(mode.value, mode.value)
            in generic_resources
        ):
            return [mode]

    return [BootMode.CPU]


def _remove_deprecated_resources(resources: ResourcesDict) -> ResourcesDict:
    for res_name in _DEPRECATED_RESOURCES:
        resources.pop(res_name, None)
    return resources


def _resources_from_settings(
    settings: list[SimcoreServiceSettingLabelEntry],
    default_service_resources: ResourcesDict,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> ResourcesDict:
    # filter resource entries
    resource_entries = filter(lambda entry: entry.name.lower() == "resources", settings)
    # get the service resources
    service_resources = deepcopy(default_service_resources)
    for entry in resource_entries:
        if not isinstance(entry.value, dict):
            _logger.warning(
                "resource %s for %s got invalid type",
                f"{entry.model_dump()!r}",
                f"{service_key}:{service_version}",
            )
            continue
        if nano_cpu_limit := entry.value.get("Limits", {}).get("NanoCPUs"):
            service_resources["CPU"].limit = nano_cpu_limit / 1.0e09
        if nano_cpu_reservation := entry.value.get("Reservations", {}).get("NanoCPUs"):
            # NOTE: if the limit was below, it needs to be increased as well
            service_resources["CPU"].limit = max(
                service_resources["CPU"].limit, nano_cpu_reservation / 1.0e09
            )
            service_resources["CPU"].reservation = nano_cpu_reservation / 1.0e09
        if ram_limit := entry.value.get("Limits", {}).get("MemoryBytes"):
            service_resources["RAM"].limit = ram_limit
        if ram_reservation := entry.value.get("Reservations", {}).get("MemoryBytes"):
            # NOTE: if the limit was below, it needs to be increased as well
            service_resources["RAM"].limit = max(
                service_resources["RAM"].limit, ram_reservation
            )
            service_resources["RAM"].reservation = ram_reservation

        service_resources |= parse_generic_resource(
            entry.value.get("Reservations", {}).get("GenericResources", []),
        )

    return _remove_deprecated_resources(service_resources)


async def _get_service_labels(
    director_client: DirectorApi, key: ServiceKey, version: ServiceVersion
) -> dict[str, Any] | None:
    try:
        service_labels = cast(
            dict[str, Any],
            await director_client.get(
                f"/services/{urllib.parse.quote_plus(key)}/{version}/labels"
            ),
        )
        _logger.debug(
            "received for %s %s",
            f"/services/{urllib.parse.quote_plus(key)}/{version}/labels",
            f"{service_labels=}",
        )
        return service_labels
    except HTTPException as err:
        # NOTE: some services will fail validation, eg:
        # `busybox:latest` or `traefik:latest` because
        # the director-v0 cannot extract labels from them
        # and will fail validating the key or the version
        if err.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
            return None
        raise


def _get_service_settings(
    labels: dict[str, Any]
) -> list[SimcoreServiceSettingLabelEntry]:
    service_settings = TypeAdapter(list[SimcoreServiceSettingLabelEntry]).validate_json(
        labels.get(SIMCORE_SERVICE_SETTINGS_LABELS, "[]"),
    )
    _logger.debug("received %s", f"{service_settings=}")
    return service_settings


@router.get(
    "/{service_key:path}/{service_version}/resources",
    response_model=ServiceResourcesDict,
    **RESPONSE_MODEL_POLICY,
)
async def get_service_resources(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    director_client: Annotated[DirectorApi, Depends(get_director_api)],
    default_service_resources: Annotated[
        ResourcesDict, Depends(get_default_service_resources)
    ],
    services_repo: Annotated[
        ServicesRepository, Depends(get_repository(ServicesRepository))
    ],
    user_groups: Annotated[list[GroupAtDB], Depends(list_user_groups)],
) -> ServiceResourcesDict:
    image_version = TypeAdapter(DockerGenericTag).validate_python(
        f"{service_key}:{service_version}"
    )
    if is_function_service(service_key):
        return ServiceResourcesDictHelpers.create_from_single_service(
            image_version, default_service_resources
        )

    service_labels: dict[str, Any] | None = await _get_service_labels(
        director_client, service_key, service_version
    )

    if not service_labels:
        return ServiceResourcesDictHelpers.create_from_single_service(
            image_version, default_service_resources
        )

    service_spec: ComposeSpecLabelDict | None = TypeAdapter(
        ComposeSpecLabelDict | None
    ).validate_json(service_labels.get(SIMCORE_SERVICE_COMPOSE_SPEC_LABEL, "null"))
    _logger.debug("received %s", f"{service_spec=}")

    if service_spec is None:
        # no compose specifications -> single service
        service_settings = _get_service_settings(service_labels)
        service_resources = _resources_from_settings(
            service_settings, default_service_resources, service_key, service_version
        )
        service_boot_modes = _compute_service_available_boot_modes(
            service_settings, service_key, service_version
        )

        user_specific_service_specs = await services_repo.get_service_specifications(
            service_key,
            service_version,
            tuple(user_groups),
            allow_use_latest_service_version=True,
        )
        if user_specific_service_specs and user_specific_service_specs.service:
            service_resources = merge_service_resources_with_user_specs(
                service_resources, user_specific_service_specs.service
            )

        return ServiceResourcesDictHelpers.create_from_single_service(
            image_version, service_resources, service_boot_modes
        )

    # compose specifications available, potentially multiple services
    stringified_service_spec = replace_env_vars_in_compose_spec(
        service_spec=service_spec,
        replace_simcore_registry="",
        replace_service_version=service_version,
    )
    full_service_spec: ComposeSpecLabelDict = yaml.safe_load(stringified_service_spec)

    service_to_resources: ServiceResourcesDict = TypeAdapter(
        ServiceResourcesDict
    ).validate_python({})

    for spec_key, spec_data in full_service_spec["services"].items():
        # image can be:
        # - `/simcore/service/dynamic/service-name:0.0.1`
        # - `traefik:0.0.1`
        # leading slashes must be stripped
        image = spec_data["image"].lstrip("/")
        key, version = image.split(":")
        spec_service_labels: dict[str, Any] | None = await _get_service_labels(
            director_client, key, version
        )

        spec_service_resources: ResourcesDict

        if not spec_service_labels:
            spec_service_resources = default_service_resources
            service_boot_modes = [BootMode.CPU]
        else:
            spec_service_settings = _get_service_settings(spec_service_labels)
            spec_service_resources = _resources_from_settings(
                spec_service_settings,
                default_service_resources,
                service_key,
                service_version,
            )
            service_boot_modes = _compute_service_available_boot_modes(
                spec_service_settings, service_key, service_version
            )
            user_specific_service_specs = (
                await services_repo.get_service_specifications(
                    key,
                    version,
                    tuple(user_groups),
                    allow_use_latest_service_version=True,
                )
            )
            if user_specific_service_specs and user_specific_service_specs.service:
                spec_service_resources = merge_service_resources_with_user_specs(
                    spec_service_resources, user_specific_service_specs.service
                )

        service_to_resources[spec_key] = ImageResources.model_validate(
            {
                "image": image,
                "resources": spec_service_resources,
                "boot_modes": service_boot_modes,
            }
        )

    return service_to_resources
