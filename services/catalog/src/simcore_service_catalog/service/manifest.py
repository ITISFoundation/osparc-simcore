"""Services Manifest API Documentation

The `service.manifest` module provides a read-only API to access the services catalog.
The term "Manifest" refers to a detailed, finalized list,
traditionally used to denote items that are recorded as part of an official inventory or log,
emphasizing the immutable nature of the data.

### Service Registration
Services are registered within the manifest in two distinct methods:

1. **Docker Registry Integration:**
   - Services can be registered by pushing a Docker image,
     complete with appropriate labels and tags, to a Docker registry.
   - These are generally services registered through the Docker registry method,
     catering primarily to end-user functionalities.
   - Example services include user-oriented applications like `sleeper`.

2. **Function Service Definition:**
   - Services can also be directly defined in the codebase as function services,
     which typically support framework operations.
   - These services are usually defined programmatically within the code and are integral
     to the framework's infrastructure.
   - Examples include utility services like `FilePicker`.


### Usage
This API is designed for read-only interactions,
allowing users to retrieve information about registered services but not to modify the registry.
This ensures data integrity and consistency across the system.


"""

import logging
from typing import Any, cast

from aiocache.base import BaseCache  # type: ignore[import-untyped]
from fastapi import HTTPException
from models_library.function_services_catalog.api import iter_service_docker_data
from models_library.services_metadata_published import ServiceMetaDataPublished
from models_library.services_types import ServiceKey, ServiceVersion
from pydantic import ValidationError
from redis.exceptions import RedisError
from servicelib.redis import CouldNotAcquireLockError, RedisClientSDK, exclusive
from servicelib.utils import limited_gather

from .._constants import DIRECTOR_CACHING_TTL
from ..clients.director import DirectorClient
from ..models.services_ports import ServicePort
from .function_services import get_function_service, is_function_service

_logger = logging.getLogger(__name__)


type ServiceMetaDataPublishedDict = dict[tuple[ServiceKey, ServiceVersion], ServiceMetaDataPublished]


_error_already_logged: set[tuple[str | None, str | None]] = set()
_SERVICE_CACHE_PREWARM_LOCK_KEY = "catalog:service_manifest:prewarm"


def _build_service_cache_key(
    *,
    key: ServiceKey,
    version: ServiceVersion,
) -> str:
    return f"get_service/{key}/{version}"


async def get_services_map(
    director_client: DirectorClient,
    service_cache: BaseCache,
) -> ServiceMetaDataPublishedDict:
    # NOTE: using Low-level API to avoid validation
    services_in_registry = cast(list[dict[str, Any]], await director_client.get("/services"))

    # NOTE: functional-services are services w/o associated image
    services: ServiceMetaDataPublishedDict = {(sc.key, sc.version): sc for sc in iter_service_docker_data()}
    for service in services_in_registry:
        try:
            service_data = ServiceMetaDataPublished.model_validate(service)
            services[service_data.key, service_data.version] = service_data

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

    try:
        await service_cache.multi_set(
            [
                (
                    _build_service_cache_key(
                        key=service.key,
                        version=service.version,
                    ),
                    service.model_dump(mode="json", by_alias=True),
                )
                for service in services.values()
            ],
            ttl=DIRECTOR_CACHING_TTL,
        )
    except (RedisError, TimeoutError):
        _logger.warning("Failed to prewarm the service manifest cache", exc_info=True)
    return services


async def get_service(
    director_client: DirectorClient,
    service_cache: BaseCache,
    *,
    key: ServiceKey,
    version: ServiceVersion,
) -> ServiceMetaDataPublished:
    """
    Retrieves service metadata from the docker registry via the director and accounting

    raises if does not exist or if validation fails
    """
    cache_key = _build_service_cache_key(key=key, version=version)
    try:
        if (cached_service := await service_cache.get(cache_key)) is not None:
            return ServiceMetaDataPublished.model_validate(cached_service)
    except (RedisError, TimeoutError):
        _logger.warning("Failed to read '%s' from the service manifest cache", cache_key, exc_info=True)

    if is_function_service(key):
        service = get_function_service(key=key, version=version)
    else:
        service = await director_client.get_service(service_key=key, service_version=version)

    try:
        await service_cache.set(
            cache_key,
            service.model_dump(mode="json", by_alias=True),
            ttl=DIRECTOR_CACHING_TTL,
        )
    except (RedisError, TimeoutError):
        _logger.warning("Failed to write '%s' to the service manifest cache", cache_key, exc_info=True)
    return service


async def _resolve_batch_service(
    *,
    key: ServiceKey,
    version: ServiceVersion,
    cached_service: Any,
    services_map: ServiceMetaDataPublishedDict,
    director_client: DirectorClient,
    service_cache: BaseCache,
) -> ServiceMetaDataPublished:
    if cached_service is not None:
        return ServiceMetaDataPublished.model_validate(cached_service)

    if service := services_map.get((key, version)):
        return service

    return await get_service(
        key=key,
        version=version,
        director_client=director_client,
        service_cache=service_cache,
    )


def _get_lock_client(*_args: Any, lock_client: RedisClientSDK, **_kwargs: Any) -> RedisClientSDK:
    return lock_client


@exclusive(
    _get_lock_client,
    lock_key=_SERVICE_CACHE_PREWARM_LOCK_KEY,
    blocking=True,
)
async def _prewarm_service_cache(
    *,
    lock_client: RedisClientSDK,
    cache_keys: list[str],
    director_client: DirectorClient,
    service_cache: BaseCache,
) -> None:
    del lock_client
    cached_services = await service_cache.multi_get(cache_keys)
    if any(cached_service is None for cached_service in cached_services):
        await get_services_map(director_client, service_cache)


async def get_batch_services(
    selection: list[tuple[ServiceKey, ServiceVersion]],
    director_client: DirectorClient,
    service_cache: BaseCache,
    *,
    lock_client: RedisClientSDK | None = None,
) -> list[ServiceMetaDataPublished | BaseException]:
    if not selection:
        return []

    cache_keys = [_build_service_cache_key(key=key, version=version) for key, version in selection]
    try:
        cached_services = cast(
            list[Any],
            await service_cache.multi_get(cache_keys),
        )
    except (RedisError, TimeoutError):
        _logger.warning("Failed to read a batch from the service manifest cache", exc_info=True)
        cached_services = [None] * len(selection)

    services_map: ServiceMetaDataPublishedDict = {}
    if any(cached_service is None for cached_service in cached_services):
        try:
            try:
                if lock_client is None:
                    services_map = await get_services_map(director_client, service_cache)
                else:
                    await _prewarm_service_cache(
                        lock_client=lock_client,
                        cache_keys=cache_keys,
                        director_client=director_client,
                        service_cache=service_cache,
                    )
                    cached_services = cast(list[Any], await service_cache.multi_get(cache_keys))
            except (CouldNotAcquireLockError, RedisError, TimeoutError):
                _logger.warning("Failed to coordinate service manifest cache prewarming", exc_info=True)
                services_map = await get_services_map(director_client, service_cache)
        except HTTPException:
            _logger.warning("Failed to prewarm the service manifest cache", exc_info=True)

    batch: list[ServiceMetaDataPublished | BaseException] = await limited_gather(
        *(
            _resolve_batch_service(
                key=key,
                version=version,
                cached_service=cached_service,
                services_map=services_map,
                director_client=director_client,
                service_cache=service_cache,
            )
            for (key, version), cached_service in zip(selection, cached_services, strict=True)
        ),
        reraise=False,
        log=_logger,
        tasks_group_prefix="manifest.get_batch_services",
    )
    return batch


async def get_service_ports(
    director_client: DirectorClient,
    service_cache: BaseCache,
    *,
    key: ServiceKey,
    version: ServiceVersion,
) -> list[ServicePort]:
    """Retrieves all ports (inputs and outputs) from a service"""
    ports = []
    service = await get_service(
        director_client=director_client,
        service_cache=service_cache,
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
