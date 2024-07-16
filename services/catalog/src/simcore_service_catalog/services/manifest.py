""" Services Manifest API Documentation

The `services.manifest` module provides a read-only API to access the services catalog. The term "Manifest" refers to a detailed, finalized list,
traditionally used to denote items that are recorded as part of an official inventory or log, emphasizing the immutable nature of the data.

### Service Registration
Services are registered within the manifest in two distinct methods:

1. **Docker Registry Integration:**
   - Services can be registered by pushing a Docker image, complete with appropriate labels and tags, to a Docker registry.
   - These are generally services registered through the Docker registry method, catering primarily to end-user functionalities.
   - Example services include user-oriented applications like `sleeper`.

2. **Function Service Definition:**
   - Services can also be directly defined in the codebase as function services, which typically support framework operations.
   - These services are usually defined programmatically within the code and are integral to the framework's infrastructure.
   - Examples include utility services like `FilePicker`.


### Usage
This API is designed for read-only interactions, allowing users to retrieve information about registered services but not to modify the registry.
This ensures data integrity and consistency across the system.


"""

import logging
from typing import Any, TypeAlias, cast

from models_library.function_services_catalog.api import iter_service_docker_data
from models_library.services_metadata_published import ServiceMetaDataPublished
from models_library.services_types import ServiceKey, ServiceVersion
from pydantic import ValidationError

from .director import DirectorApi
from .function_services import get_function_service, is_function_service

_logger = logging.getLogger(__name__)


ServiceMetaDataPublishedDict: TypeAlias = dict[
    tuple[ServiceKey, ServiceVersion], ServiceMetaDataPublished
]


_error_already_logged: set[tuple[str | None, str | None]] = set()


async def get_services_map(
    director_client: DirectorApi,
) -> ServiceMetaDataPublishedDict:

    # NOTE: using Low-level API to avoid validation
    services_in_registry = cast(
        list[dict[str, Any]], await director_client.get("/services")
    )

    # NOTE: functional-services are services w/o associated image
    services: ServiceMetaDataPublishedDict = {
        (s.key, s.version): s for s in iter_service_docker_data()
    }
    for service in services_in_registry:
        try:
            service_data = ServiceMetaDataPublished.parse_obj(service)
            services[(service_data.key, service_data.version)] = service_data

        except ValidationError:  # noqa: PERF203
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


async def get_service(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    director_client: DirectorApi,
) -> ServiceMetaDataPublished:
    """
    Retrieves service metadata from the docker registry via the director and accounting
    """
    if is_function_service(service_key):
        service = get_function_service(key=service_key, version=service_version)
    else:
        service = await director_client.get_service(
            service_key=service_key, service_version=service_version
        )
    return service
