import logging
import urllib.parse
from typing import Any, cast

from aiocache import cached
from fastapi import APIRouter, Depends
from models_library.service_settings_labels import SimcoreServiceSettingLabelEntry
from models_library.services import ServiceKey, ServiceVersion
from models_library.services_resources import (
    ResourceName,
    ResourceValue,
    ServiceResources,
)
from pydantic import parse_raw_as

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
    response_model=dict[ResourceName, ResourceValue],
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
    default_service_resources: ServiceResources = Depends(
        get_default_service_resources
    ),
):
    # cause these entries are not in ServiceDockerData
    if is_function_service(service_key):
        # NOTE: this is due to the fact that FastAPI does not appear to like pydantic models with just a root
        return default_service_resources.dict()["__root__"]

    service_labels: dict[str, Any] = cast(
        dict[str, Any],
        await director_client.get(
            f"/services/{urllib.parse.quote_plus(service_key)}/{service_version}/labels"
        ),
    )

    if not service_labels:
        # NOTE: this is due to the fact that FastAPI does not appear to like pydantic models with just a root
        return default_service_resources.dict()["__root__"]

    service_settings = parse_raw_as(
        list[SimcoreServiceSettingLabelEntry],
        service_labels.get(SIMCORE_SERVICE_SETTINGS_LABELS, ""),
    )
    logger.debug("received %s", f"{service_settings}")

    service_resources = _from_service_settings(
        service_settings, service_key, service_version, default_service_resources
    )
    logger.debug("%s", f"{service_resources}")
    # NOTE: this is due to the fact that FastAPI does not appear to like pydantic models with just a root
    return service_resources.dict()["__root__"]
