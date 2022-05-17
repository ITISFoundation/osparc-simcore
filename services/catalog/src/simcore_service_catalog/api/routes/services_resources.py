import logging
import urllib.parse
from typing import Any, Final, List, Optional, cast

import yaml
from aiocache import cached
from fastapi import APIRouter, Depends
from models_library.service_settings_labels import (
    ComposeSpecLabel,
    SimcoreServiceSettingLabelEntry,
)
from models_library.services import ServiceKey, ServiceVersion
from models_library.services_resources import (
    ImageResources,
    ResourcesDict,
    ResourceValue,
    ServiceResources,
)
from pydantic import parse_raw_as
from servicelib.docker_compose import replace_env_vars_in_compose_spec

from ...models.schemas.constants import (
    DIRECTOR_CACHING_TTL,
    RESPONSE_MODEL_POLICY,
    SIMCORE_SERVICE_SETTINGS_LABELS,
)
from ...services.function_services import is_function_service
from ..dependencies.director import DirectorApi, get_director_api
from ..dependencies.services import get_default_service_resources

router = APIRouter()
logger = logging.getLogger(__name__)

SIMCORE_SERVICE_SETTINGS_LABELS: Final[str] = "simcore.service.settings"
SIMCORE_SERVICE_COMPOSE_SPEC_LABEL: Final[str] = "simcore.service.compose-spec"


def _parse_generic_resource(
    generic_resources: list[Any], service_resources: ServiceResources
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
    service_key: ServiceKey,
    service_version: ServiceVersion,
    default_service_resources: ServiceResources,
) -> ServiceResources:
    # filter resource entries
    resource_entries = filter(lambda entry: entry.name.lower() == "resources", settings)
    # get the service resources
    service_resources = default_service_resources.copy(deep=True)
    for entry in resource_entries:
        if not isinstance(entry.value, dict):
            logger.warning(
                "resource %s for %s got invalid type, skipping it",
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


@router.get(
    "/{service_key:path}/{service_version}/resources",
    response_model=ServiceResources,
    **RESPONSE_MODEL_POLICY,
)
@cached(
    ttl=DIRECTOR_CACHING_TTL,
    key_builder=lambda f, *args, **kwargs: f"{f.__name__}_{kwargs['service_key']}_{kwargs['service_version']}",
)
async def get_service_resources(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    director_client: DirectorApi = Depends(get_director_api),
    default_service_resources: ResourcesDict = Depends(get_default_service_resources),
) -> ServiceResources:
    # TODO: --> PC: I'll need to go through that with you for function services,
    # cause these entries are not in ServiceDockerData

    image_version = f"{service_key}:{service_version}"
    if is_function_service(service_key):
        return ServiceResources.from_resources(default_service_resources, image_version)

    def _from_service_settings(
        settings: List[SimcoreServiceSettingLabelEntry],
    ) -> ResourcesDict:
        # filter resource entries
        resource_entries = filter(
            lambda entry: entry.name.lower() == "resources", settings
        )
        # get the service resources
        service_resources = default_service_resources.copy(deep=True)
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
            if nano_cpu_reservation := entry.value.get("Reservations", {}).get(
                "NanoCPUs"
            ):
                service_resources["CPU"].reservation = nano_cpu_reservation / 1.0e09
            if ram_limit := entry.value.get("Limits", {}).get("MemoryBytes"):
                service_resources["RAM"].limit = ram_limit
            if ram_reservation := entry.value.get("Reservations", {}).get(
                "MemoryBytes"
            ):
                service_resources["RAM"].reservation = ram_reservation

            if generic_resources := entry.value.get("Reservations", {}).get(
                "GenericResources", []
            ):
                for res in generic_resources:
                    if not isinstance(res, dict):
                        continue

                    if named_resource_spec := res.get("NamedResourceSpec"):
                        service_resources.setdefault(
                            named_resource_spec["Kind"],
                            ResourceValue(
                                limit=0, reservation=named_resource_spec["Value"]
                            ),
                        ).reservation = named_resource_spec["Value"]
                    if discrete_resource_spec := res.get("DiscreteResourceSpec"):
                        service_resources.setdefault(
                            discrete_resource_spec["Kind"],
                            ResourceValue(
                                limit=0, reservation=discrete_resource_spec["Value"]
                            ),
                        ).reservation = discrete_resource_spec["Value"]

        return service_resources

    async def _get_service_labels(key: str, version: str) -> dict[str, Any]:
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

    def _get_service_settings(
        labels: dict[str, Any]
    ) -> List[SimcoreServiceSettingLabelEntry]:
        service_settings = parse_raw_as(
            List[SimcoreServiceSettingLabelEntry],
            labels.get(SIMCORE_SERVICE_SETTINGS_LABELS, ""),
        )
        logger.debug("received %s", f"{service_settings=}")
        return service_settings

    service_labels: dict[str, Any] = await _get_service_labels(
        service_key, service_version
    )

    if not service_labels:
        return ServiceResources.from_resources(default_service_resources, image_version)

    service_spec: Optional[ComposeSpecLabel] = parse_raw_as(
        Optional[ComposeSpecLabel],
        service_labels.get(SIMCORE_SERVICE_COMPOSE_SPEC_LABEL, "null"),
    )
    logger.debug("received %s", f"{service_spec=}")

    if service_spec is None:
        service_settings = _get_service_settings(service_labels)
        service_resources = _from_service_settings(service_settings)
        return ServiceResources.from_resources(service_resources, image_version)

    stringified_service_spec = replace_env_vars_in_compose_spec(
        service_spec=service_spec,
        replace_simcore_registry="",
        replace_service_version=service_version,
    )
    full_service_spec: ComposeSpecLabel = yaml.safe_load(stringified_service_spec)

    results: ServiceResources = ServiceResources.parse_obj({})

    for spec_key, spec_data in full_service_spec["services"].items():
        # image can be:
        # - `/simcore/service/dynamic/service-name:0.0.1`
        # - `traefik:0.0.1`
        # leading slashes must be stripped
        image = spec_data["image"].lstrip("/")
        key, version = image.split(":")
        spec_service_labels: dict[str, Any] = await _get_service_labels(key, version)

        if not spec_service_labels:
            spec_service_resources: ResourcesDict = default_service_resources
        else:
            spec_service_settings = _get_service_settings(spec_service_labels)
            spec_service_resources: ResourcesDict = _from_service_settings(
                spec_service_settings
            )

        results[spec_key] = ImageResources.parse_obj(
            {"image": image, "resources": spec_service_resources}
        )

    return results
