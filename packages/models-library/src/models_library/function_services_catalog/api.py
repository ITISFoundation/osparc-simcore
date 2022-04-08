"""
    Factory to build catalog of i/o metadata for functions implemented in the front-end

    NOTE: These definitions are currently needed in the catalog and director2
    services. Since it is static data, instead of making a call from
    director2->catalog, it was decided to share as a library
"""

from typing import Iterator, Tuple

from ..services import ServiceDockerData
from . import _registry
from ._key_labels import is_function_service


def iter_service_docker_data() -> Iterator[ServiceDockerData]:
    for meta_obj in _registry.CATALOG_REGISTRY.values():
        # NOTE: the originals are this way not modified from outside
        copied_meta_obj = meta_obj.copy(deep=True)
        assert is_function_service(copied_meta_obj.key)  # nosec
        yield copied_meta_obj


__all__: Tuple[str, ...] = (
    "iter_service_docker_data",
    "FUNCTION_SERVICE_KEY_PREFIX",
    "is_function_service",
)
