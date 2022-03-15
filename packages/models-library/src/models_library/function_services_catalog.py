"""
    Factory to build catalog of i/o metadata for functions implemented in the front-end

    NOTE: These definitions are currently needed in the catalog and director2
    services. Since it is static data, instead of making a call from
    director2->catalog, it was decided to share as a library
"""

import logging
from typing import Iterator

from .function_service import (
    demo_units,
    file_picker,
    iter_range,
    iter_sensitivity,
    nodes_group,
    parameters,
    probes,
)
from .function_service.constants import FUNCTION_SERVICE_KEY_PREFIX
from .services import ServiceDockerData

logger = logging.getLogger(__name__)


# CATALOG REGISTRY ----------------------------------------------------


def create_registry(*namespaces):
    _registry = {}
    for namespace in namespaces:
        try:
            for (node_key, node_version), meta in namespace.REGISTRY.items():

                if (node_key, node_version) in _registry:
                    raise ValueError(
                        f"{(node_key, node_version)=} is already registered"
                    )

                _registry[
                    (node_key, node_version),
                ] = meta
        except (ValueError, AttributeError):
            logger.error("Failed to register functions in %s. Skipping", namespace)
    return _registry


_CATALOG_REGISTRY = create_registry(
    demo_units,
    file_picker,
    iter_range,
    iter_sensitivity,
    nodes_group,
    parameters,
    probes,
)


def iter_service_docker_data() -> Iterator[ServiceDockerData]:
    for meta_obj in _CATALOG_REGISTRY.values():
        # NOTE: the originals are this way not modified from outside
        copied_meta_obj = meta_obj.copy(deep=True)
        assert is_function_service(copied_meta_obj.key)  # nosec
        yield copied_meta_obj


# HELPER --------------------------------------


def is_function_service(service_key: str) -> bool:
    return service_key.startswith(f"{FUNCTION_SERVICE_KEY_PREFIX}/")


def is_parameter_service(service_key: str) -> bool:
    return service_key.startswith(f"{FUNCTION_SERVICE_KEY_PREFIX}/parameter/")


def is_iterator_service(service_key: str) -> bool:
    return service_key.startswith(f"{FUNCTION_SERVICE_KEY_PREFIX}/data-iterator/")


def is_iterator_consumer_service(service_key: str) -> bool:
    return service_key.startswith(f"{FUNCTION_SERVICE_KEY_PREFIX}/iterator-consumer/")
