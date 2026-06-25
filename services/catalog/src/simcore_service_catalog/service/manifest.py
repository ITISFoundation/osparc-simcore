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

from .._constants import DIRECTOR_CACHING_TTL
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


_SERVICE_CACHE_KEY: Final = "service"
_SERVICES_MAP_CACHE_KEY: Final = "services_map"


def _get_or_create_cache(
    director_client: DirectorClient,
    name: str,
    populate: Any,
    key_builder: Any,
) -> Any:
    # NOTE: the cache is attached to the *director client instance* so that distinct
    # apps never share cache state. It is built lazily (once per client).
    # `_uuid` namespaces each client's entries in aiocache's in-memory store.
    cached_fn = director_client.services_caches.get(name)
    if cached_fn is None:
        cached_fn = cached_stampede(
            ttl=DIRECTOR_CACHING_TTL,
            lease=director_client.services_cache_lease,
            namespace=f"{__name__}:{director_client._uuid}",  # noqa: SLF001
            key_builder=key_builder,
            skip_cache_func=lambda _result: not director_client.services_caching_enabled,
        )(populate)
        director_client.services_caches[name] = cached_fn
    return cached_fn


async def reset_services_caches(director_client: DirectorClient) -> None:
    # NOTE: clears this client's manifest caches and drops the cached callables so that
    # they are rebuilt from the client's current configuration (e.g. after changing the
    # lease). Mainly used for test isolation / forcing a cold cache.
    for cached_fn in director_client.services_caches.values():
        await cached_fn.cache.clear()
    director_client.services_caches.clear()


async def _populate_service(
    director_client: DirectorClient,
    *,
    key: ServiceKey,
    version: ServiceVersion,
) -> ServiceMetaDataPublished:
    if is_function_service(key):
        return get_function_service(key=key, version=version)
    return await director_client.get_service(service_key=key, service_version=version)


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
    cached_fn = _get_or_create_cache(
        director_client,
        _SERVICE_CACHE_KEY,
        _populate_service,
        lambda f, *_args, **kw: f"{f.__name__}/{kw['key']}/{kw['version']}",
    )
    return await cached_fn(director_client, key=key, version=version)


async def _populate_services_map(
    director_client: DirectorClient,
) -> ServiceMetaDataPublishedDict:
    # NOTE: caches the *entire* registry manifest so that resolving a batch of
    # services requires a single director call instead of one call per service.
    return await get_services_map(director_client)


async def get_batch_services(
    selection: list[tuple[ServiceKey, ServiceVersion]],
    director_client: DirectorClient,
) -> list[ServiceMetaDataPublished | BaseException]:
    # NOTE: resolves the whole manifest in a single (cached) bulk fetch and looks
    # up the selection, avoiding a per-service fan-out of director calls.
    cached_fn = _get_or_create_cache(
        director_client,
        _SERVICES_MAP_CACHE_KEY,
        _populate_services_map,
        lambda f, *_args, **_kwargs: f.__name__,
    )
    services_map = await cached_fn(director_client)
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
