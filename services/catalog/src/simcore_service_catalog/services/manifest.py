"""  service manifest API

Manifest: A detailed list, historically used to describe items being entered or shipped, implying finalized data (i.e. READ-ONLY)

Services can be included in the manifest in TWO possible ways:
    - pushing an image w/ labels+tags in a `docker registry` (e.g. sleeper,...)
    - defining a `function service` in the code (e.g. FilePicker, ...)

The first type of services are mostly "user services" while the second is mostly "framework services".
"""

import logging
from typing import Any, TypeAlias, cast

from models_library.function_services_catalog.api import iter_service_docker_data
from models_library.services_metadata_published import ServiceMetaDataPublished
from models_library.services_types import ServiceKey, ServiceVersion
from pydantic import ValidationError

from .director import DirectorApi
from .function_services import get_function_service_as_model, is_function_service

_logger = logging.getLogger(__name__)


ServiceMetaDataPublishedMap: TypeAlias = dict[
    tuple[ServiceKey, ServiceVersion], ServiceMetaDataPublished
]


_error_already_logged: set[tuple[str, str]] = set()


async def get_services_map(
    director_client: DirectorApi,
) -> ServiceMetaDataPublishedMap:
    """Lists all services registered either in code (functional services) or the docker registry"""
    registry_services = cast(
        list[dict[str, Any]], await director_client.get("/services")
    )

    # NOTE: functional-services are services w/o associated image
    services: ServiceMetaDataPublishedMap = {
        (s.key, s.version): s for s in iter_service_docker_data()
    }
    for service in registry_services:
        try:
            service_data = ServiceMetaDataPublished.parse_obj(service)
            services[(service_data.key, service_data.version)] = service_data

        except ValidationError:  # noqa: PERF203
            # NOTE: this is necessary until director API response does NOT provides any guarantee

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
        service = get_function_service_as_model(
            key=service_key, version=service_version
        )
    else:
        service = await director_client.get_service(
            service_key=service_key, service_version=service_version
        )
    return service
