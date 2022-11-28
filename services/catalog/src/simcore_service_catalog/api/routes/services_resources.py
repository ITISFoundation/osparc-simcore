import logging
import urllib.parse
from copy import deepcopy
from typing import Any, Final, Optional, cast

import yaml
from aiocache import cached
from fastapi import APIRouter, Depends, HTTPException, status
from models_library.docker import DockerImageKey, DockerImageVersion
from models_library.service_settings_labels import (
    ComposeSpecLabel,
    SimcoreServiceSettingLabelEntry,
)
from models_library.services_resources import (
    ImageResources,
    ResourcesDict,
    ResourceValue,
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from pydantic import parse_obj_as, parse_raw_as
from servicelib.docker_compose import replace_env_vars_in_compose_spec

from ...db.repositories.groups import GroupsRepository
from ...db.repositories.services import ServicesRepository
from ...models.domain.group import GroupAtDB
from ...models.schemas.constants import (
    DIRECTOR_CACHING_TTL,
    RESPONSE_MODEL_POLICY,
    SIMCORE_SERVICE_SETTINGS_LABELS,
)
from ...services.function_services import is_function_service
from ..dependencies.database import get_repository
from ..dependencies.director import DirectorApi, get_director_api
from ..dependencies.services import get_default_service_resources
from ..dependencies.user_groups import list_user_groups

router = APIRouter()
logger = logging.getLogger(__name__)

SIMCORE_SERVICE_SETTINGS_LABELS: Final[str] = "simcore.service.settings"
SIMCORE_SERVICE_COMPOSE_SPEC_LABEL: Final[str] = "simcore.service.compose-spec"


def _parse_generic_resource(
    generic_resources: list[Any], service_resources: ResourcesDict
) -> None:
    for res in generic_resources:
        if not isinstance(res, dict):
            continue

        if named_resource_spec := res.get("NamedResourceSpec"):
            service_resources.setdefault(
                named_resource_spec["Kind"],
                ResourceValue(limit=0, reservation=named_resource_spec["Value"]),
            ).reservation = named_resource_spec["Value"]
        if discrete_resource_spec := res.get("DiscreteResourceSpec"):
            service_resources.setdefault(
                discrete_resource_spec["Kind"],
                ResourceValue(limit=0, reservation=discrete_resource_spec["Value"]),
            ).reservation = discrete_resource_spec["Value"]


def _from_service_settings(
    settings: list[SimcoreServiceSettingLabelEntry],
    default_service_resources: ResourcesDict,
    service_key: DockerImageKey,
    service_version: DockerImageVersion,
) -> ResourcesDict:
    # filter resource entries
    resource_entries = filter(lambda entry: entry.name.lower() == "resources", settings)
    # get the service resources
    service_resources = deepcopy(default_service_resources)
    for entry in resource_entries:
        if not isinstance(entry.value, dict):
            logger.warning(
                "resource %s for %s got invalid type",
                f"{entry.dict()!r}",
                f"{service_key}:{service_version}",
            )
            continue
        if nano_cpu_limit := entry.value.get("Limits", {}).get("NanoCPUs"):
            service_resources["CPU"].limit = nano_cpu_limit / 1.0e09
        if nano_cpu_reservation := entry.value.get("Reservations", {}).get("NanoCPUs"):
            service_resources["CPU"].reservation = nano_cpu_reservation / 1.0e09
        if ram_limit := entry.value.get("Limits", {}).get("MemoryBytes"):
            service_resources["RAM"].limit = ram_limit
        if ram_reservation := entry.value.get("Reservations", {}).get("MemoryBytes"):
            service_resources["RAM"].reservation = ram_reservation

        _parse_generic_resource(
            entry.value.get("Reservations", {}).get("GenericResources", []),
            service_resources,
        )

    return service_resources


async def _get_service_labels(
    director_client: DirectorApi, key: DockerImageKey, version: DockerImageVersion
) -> Optional[dict[str, Any]]:
    try:
        service_labels = cast(
            dict[str, Any],
            await director_client.get(
                f"/services/{urllib.parse.quote_plus(key)}/{version}/labels"
            ),
        )
        logger.debug(
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
        if err.status_code == status.HTTP_400_BAD_REQUEST:
            return None
        raise err


def _get_service_settings(
    labels: dict[str, Any]
) -> list[SimcoreServiceSettingLabelEntry]:
    service_settings = parse_raw_as(
        list[SimcoreServiceSettingLabelEntry],
        labels.get(SIMCORE_SERVICE_SETTINGS_LABELS, ""),
    )
    logger.debug("received %s", f"{service_settings=}")
    return service_settings


@router.get(
    "/{service_key:path}/{service_version}/resources",
    response_model=ServiceResourcesDict,
    **RESPONSE_MODEL_POLICY,
)
@cached(
    ttl=DIRECTOR_CACHING_TTL,
    key_builder=lambda f, *args, **kwargs: f"{f.__name__}_{kwargs.get('user_id', 'default')}_{kwargs['service_key']}_{kwargs['service_version']}",
)
async def get_service_resources(
    service_key: DockerImageKey,
    service_version: DockerImageVersion,
    director_client: DirectorApi = Depends(get_director_api),
    default_service_resources: ResourcesDict = Depends(get_default_service_resources),
    groups_repository: GroupsRepository = Depends(get_repository(GroupsRepository)),
    services_repo: ServicesRepository = Depends(get_repository(ServicesRepository)),
    user_groups: list[GroupAtDB] = Depends(list_user_groups),
) -> ServiceResourcesDict:
    image_version = f"{service_key}:{service_version}"
    if is_function_service(service_key):
        return ServiceResourcesDictHelpers.create_from_single_service(
            image_version, default_service_resources
        )

    service_labels: Optional[dict[str, Any]] = await _get_service_labels(
        director_client, service_key, service_version
    )

    if not service_labels:
        return ServiceResourcesDictHelpers.create_from_single_service(
            image_version, default_service_resources
        )

    service_spec: Optional[ComposeSpecLabel] = parse_raw_as(
        Optional[ComposeSpecLabel],
        service_labels.get(SIMCORE_SERVICE_COMPOSE_SPEC_LABEL, "null"),
    )
    logger.debug("received %s", f"{service_spec=}")

    if service_spec is None:
        # no compose specifications -> single service
        service_settings = _get_service_settings(service_labels)
        service_resources = _from_service_settings(
            service_settings, default_service_resources, service_key, service_version
        )
        user_specific_service_specs = await services_repo.get_service_specifications(
            service_key,
            service_version,
            tuple(user_groups),
            allow_use_latest_service_version=True,
        )

        # TODO: merge with user specific settings here
        return ServiceResourcesDictHelpers.create_from_single_service(
            image_version, service_resources
        )

    # compose specifications available, potentially multiple services
    stringified_service_spec = replace_env_vars_in_compose_spec(
        service_spec=service_spec,
        replace_simcore_registry="",
        replace_service_version=service_version,
    )
    full_service_spec: ComposeSpecLabel = yaml.safe_load(stringified_service_spec)

    service_to_resources: ServiceResourcesDict = parse_obj_as(ServiceResourcesDict, {})

    for spec_key, spec_data in full_service_spec["services"].items():
        # image can be:
        # - `/simcore/service/dynamic/service-name:0.0.1`
        # - `traefik:0.0.1`
        # leading slashes must be stripped
        image = spec_data["image"].lstrip("/")
        key, version = image.split(":")
        spec_service_labels: Optional[dict[str, Any]] = await _get_service_labels(
            director_client, key, version
        )

        if not spec_service_labels:
            spec_service_resources: ResourcesDict = default_service_resources
        else:
            spec_service_settings = _get_service_settings(spec_service_labels)
            spec_service_resources: ResourcesDict = _from_service_settings(
                spec_service_settings,
                default_service_resources,
                service_key,
                service_version,
            )
            user_specific_service_specs = (
                await services_repo.get_service_specifications(
                    service_key,
                    service_version,
                    tuple(user_groups),
                    allow_use_latest_service_version=True,
                )
            )

        # TODO: merge with user specific settings here
        service_to_resources[spec_key] = ImageResources.parse_obj(
            {"image": image, "resources": spec_service_resources}
        )

    return service_to_resources
