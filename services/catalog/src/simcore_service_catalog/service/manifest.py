"""Services Manifest API Documentation

The `service.manifest` module provides a read-only API to access the services catalog. The term "Manifest"
refers to a detailed, finalized list, traditionally used to denote items that are recorded as part of an
official inventory or log, emphasizing the immutable nature of the data.

### Service Registration
Services are registered within the manifest in two distinct methods:

1. **Docker Registry Integration:**
   - Services can be registered by pushing a Docker image, complete with appropriate labels and tags,
     to a Docker registry.
   - These are generally services registered through the Docker registry method, catering primarily to
     end-user functionalities.
   - Example services include user-oriented applications like `sleeper`.

2. **Function Service Definition:**
   - Services can also be directly defined in the codebase as function services, which typically support
     framework operations.
   - These services are usually defined programmatically within the code and are integral to the
     framework's infrastructure.
   - Examples include utility services like `FilePicker`.


### Usage
This API is designed for read-only interactions, allowing users to retrieve information about registered
services but not to modify the registry. This ensures data integrity and consistency across the system.


"""

import logging
from typing import Any, Final, cast

from aiocache.decorators import cached_stampede  # type: ignore[import-untyped]
from models_library.function_services_catalog.api import iter_service_docker_data
from models_library.services_metadata_published import ServiceMetaDataPublished
from models_library.services_types import ServiceKey, ServiceVersion
from pydantic import ValidationError

from .._constants import DEFAULT_DIRECTOR_BULK_FETCH_LEASE, DIRECTOR_CACHING_TTL
from ..clients.director import DirectorClient
from ..models.services_ports import ServicePort
from .function_services import get_function_service, is_function_service

_logger = logging.getLogger(__name__)


type ServiceMetaDataPublishedDict = dict[tuple[ServiceKey, ServiceVersion], ServiceMetaDataPublished]


_error_already_logged: set[tuple[str | None, str | None]] = set()


async def get_services_map(
    director_client: DirectorClient,
) -> ServiceMetaDataPublishedDict:
    # NOTE: using Low-level API to avoid validation
    services_in_registry = cast(list[dict[str, Any]], await director_client.get("/services"))

    # NOTE: functional-services are services w/o associated image
    services: ServiceMetaDataPublishedDict = {(sc.key, sc.version): sc for sc in iter_service_docker_data()}
    for service in services_in_registry:
        try:
            service_data = ServiceMetaDataPublished.model_validate(service)
            services[(service_data.key, service_data.version)] = service_data

        except ValidationError:
            # NOTE: this is necessary since registry DOES NOT provides any guarantee of the meta-data
            # in the labels, i.e. it is not validated
            errored_service = (service.get("key"), service.get("version"))
            if errored_service not in _error_already_logged:
                _logger.warning(
                    "Skipping '%s:%s' from the catalog of services! So far %s invalid services in registry.",
                    *errored_service,
                    len(_error_already_logged) + 1,
                    exc_info=True,
                )
                _error_already_logged.add(errored_service)

    return services


_get_service_cache: Final = cached_stampede(
    ttl=DIRECTOR_CACHING_TTL,
    # NOTE: `lease` coalesces a cold-cache burst for the *same* service into a single
    # director call (the others await the in-flight populate), avoiding a stampede.
    # It is reconfigured from settings at startup (see `set_services_cache_lease`).
    lease=DEFAULT_DIRECTOR_BULK_FETCH_LEASE,
    namespace=__name__,
    key_builder=lambda f, *_args, **kw: f"{f.__name__}/{kw['key']}/{kw['version']}",
)


@_get_service_cache
async def get_service(
    director_client: DirectorClient,
    *,
    key: ServiceKey,
    version: ServiceVersion,
) -> ServiceMetaDataPublished:
    """
    Retrieves service metadata from the docker registry via the director and accounting

    raises if does not exist or if validation fails
    """
    if is_function_service(key):
        service = get_function_service(key=key, version=version)
    else:
        service = await director_client.get_service(service_key=key, service_version=version)
    return service


_get_cached_services_map_cache: Final = cached_stampede(
    ttl=DIRECTOR_CACHING_TTL,
    # NOTE: `lease` locks the populate step so that a burst of concurrent calls on a
    # cold cache results in a *single* director bulk fetch (the others await the
    # in-flight populate and read the freshly cached value) instead of a thundering herd.
    # It is reconfigured from settings at startup (see `set_services_cache_lease`).
    lease=DEFAULT_DIRECTOR_BULK_FETCH_LEASE,
    namespace=__name__,
    key_builder=lambda f, *_args, **_kwargs: f.__name__,
)


@_get_cached_services_map_cache
async def _get_cached_services_map(
    director_client: DirectorClient,
) -> ServiceMetaDataPublishedDict:
    # NOTE: caches the *entire* registry manifest so that resolving a batch of
    # services requires a single director call instead of one call per service.
    return await get_services_map(director_client)


def set_services_cache_lease(lease_seconds: float) -> None:
    # NOTE: aiocache binds `lease` when the cache decorators above are created at import
    # time, so the value coming from settings is applied here at application startup.
    _get_service_cache.lease = lease_seconds
    _get_cached_services_map_cache.lease = lease_seconds


async def get_batch_services(
    selection: list[tuple[ServiceKey, ServiceVersion]],
    director_client: DirectorClient,
) -> list[ServiceMetaDataPublished | BaseException]:
    # NOTE: resolves the whole manifest in a single (cached) bulk fetch and looks
    # up the selection, avoiding a per-service fan-out of director calls.
    services_map = await _get_cached_services_map(director_client=director_client)
    batch: list[ServiceMetaDataPublished | BaseException] = []
    for key, version in selection:
        service = services_map.get((key, version))
        batch.append(service if service is not None else KeyError((key, version)))
    return batch


async def get_service_ports(
    director_client: DirectorClient,
    *,
    key: ServiceKey,
    version: ServiceVersion,
) -> list[ServicePort]:
    """Retrieves all ports (inputs and outputs) from a service"""
    ports = []
    service = await get_service(
        director_client=director_client,
        key=key,
        version=version,
    )

    if service.inputs:
        for input_name, service_input in service.inputs.items():
            ports.append(
                ServicePort(
                    kind="input",
                    key=input_name,
                    port=service_input,
                )
            )

    if service.outputs:
        for output_name, service_output in service.outputs.items():
            ports.append(
                ServicePort(
                    kind="output",
                    key=output_name,
                    port=service_output,
                )
            )

    return ports
