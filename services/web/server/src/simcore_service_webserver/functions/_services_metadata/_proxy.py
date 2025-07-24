from collections.abc import Iterable

from aiohttp import web
from models_library.services_types import ServiceKey, ServiceVersion

from . import _repository
from ._models import ServiceMetadata


async def batch_get_service_metadata(
    app: web.Application,
    *,
    keys_and_versions: Iterable[tuple[ServiceKey, ServiceVersion]],
) -> dict[tuple[ServiceKey, ServiceVersion], ServiceMetadata]:
    return await _repository.batch_service_metadata(
        app, keys_and_versions=keys_and_versions
    )


async def get_service_metadata(
    app: web.Application,
    *,
    key: ServiceKey,
    version: ServiceVersion,
) -> ServiceMetadata:
    return await _repository.get_service_metadata(app, key=key, version=version)
