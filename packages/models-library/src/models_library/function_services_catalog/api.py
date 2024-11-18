# mypy: disable-error-code=truthy-function
"""
    Factory to build catalog of i/o metadata for functions implemented in the front-end

    NOTE: These definitions are currently needed in the catalog and director2
    services. Since it is static data, instead of making a call from
    director2->catalog, it was decided to share as a library
"""

from collections.abc import Iterator

from ..services import ServiceMetaDataPublished
from ._key_labels import is_function_service, is_iterator_service
from ._registry import catalog
from .services.parameters import is_parameter_service
from .services.probes import is_probe_service

assert catalog  # nosec
assert is_iterator_service  # nosec
assert is_parameter_service  # nosec
assert is_probe_service  # nosec


def iter_service_docker_data() -> Iterator[ServiceMetaDataPublished]:
    for meta_obj in catalog.iter_metadata():
        # NOTE: the originals are this way not modified from outside
        copied_meta_obj = meta_obj.model_copy(deep=True)
        assert is_function_service(copied_meta_obj.key)  # nosec
        yield copied_meta_obj


__all__: tuple[str, ...] = (
    "catalog",
    "is_function_service",
    "is_iterator_service",
    "is_parameter_service",
    "is_probe_service",
    "iter_service_docker_data",
)
