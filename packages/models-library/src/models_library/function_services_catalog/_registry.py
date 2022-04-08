"""
    Factory to build catalog of i/o metadata for functions implemented in the front-end

    NOTE: These definitions are currently needed in the catalog and director2
    services. Since it is static data, instead of making a call from
    director2->catalog, it was decided to share as a library
"""

import logging
from typing import Dict

from .services import (
    demo_units,
    file_picker,
    iter_range,
    iter_sensitivity,
    parameters,
    probes,
)

logger = logging.getLogger(__name__)


def _create_registry(*namespaces):
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


CATALOG_REGISTRY: Dict = _create_registry(
    demo_units,
    file_picker,
    iter_range,
    iter_sensitivity,
    parameters,
    probes,
)
