import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from urllib.parse import quote

from ..services import Author, ServiceKey, ServiceMetaDataPublished, ServiceVersion
from ._settings import AUTHORS, FunctionServiceSettings

_logger = logging.getLogger(__name__)


_DEFAULT = {
    "name": "Unknown",
    "email": "unknown@osparc.io",
    "affiliation": "unknown",
}
EN = Author.model_validate(AUTHORS.get("EN", _DEFAULT))
OM = Author.model_validate(AUTHORS.get("OM", _DEFAULT))
PC = Author.model_validate(AUTHORS.get("PC", _DEFAULT))
WVG = Author.model_validate(AUTHORS.get("WVG", _DEFAULT))


def create_fake_thumbnail_url(label: str) -> str:
    return f"https://fakeimg.pl/100x100/ff0000%2C128/000%2C255/?text={quote(label)}"


class ServiceNotFound(KeyError):
    pass


@dataclass
class _Record:
    meta: ServiceMetaDataPublished
    implementation: Callable | None = None
    is_under_development: bool = False


class FunctionServices:
    """Used to register a collection of function services"""

    def __init__(self, settings: FunctionServiceSettings | None = None):
        self._functions: dict[tuple[ServiceKey, ServiceVersion], _Record] = {}
        self.settings = settings

    def add(
        self,
        meta: ServiceMetaDataPublished,
        implementation: Callable | None = None,
        is_under_development: bool = False,
    ):
        """
        raises ValueError
        """
        if not isinstance(meta, ServiceMetaDataPublished):
            msg = f"Expected ServiceDockerData, got {type(meta)}"
            raise ValueError(msg)

        # ensure unique
        if (meta.key, meta.version) in self._functions:
            msg = f"{meta.key, meta.version} is already registered"
            raise ValueError(msg)

        # TODO: ensure callable signature fits metadata

        # register
        self._functions[(meta.key, meta.version)] = _Record(
            meta=meta,
            implementation=implementation,
            is_under_development=is_under_development,
        )

    def extend(self, other: "FunctionServices"):
        # pylint: disable=protected-access
        for f in other._functions.values():
            self.add(f.meta, f.implementation, f.is_under_development)

    def _skip_dev(self):
        skip = True
        if self.settings:
            skip = not self.settings.is_dev_feature_enabled()
        return skip

    def _items(
        self,
    ) -> Iterator[tuple[tuple[ServiceKey, ServiceVersion], _Record]]:
        skip_dev = self._skip_dev()
        for key, value in self._functions.items():
            if value.is_under_development and skip_dev:
                continue
            yield key, value

    def iter_metadata(self) -> Iterator[ServiceMetaDataPublished]:
        """WARNING: this function might skip services marked as 'under development'"""
        for _, f in self._items():
            yield f.meta

    def iter_services_key_version(
        self,
    ) -> Iterator[tuple[ServiceKey, ServiceVersion]]:
        """WARNING: this function might skip services makred as 'under development'"""
        for kv, f in self._items():
            assert kv == (f.meta.key, f.meta.version)  # nosec
            yield kv

    def get_implementation(
        self, service_key: ServiceKey, service_version: ServiceVersion
    ) -> Callable | None:
        """raises ServiceNotFound"""
        try:
            func = self._functions[(service_key, service_version)]
        except KeyError as err:
            msg = f"{service_key}:{service_version} not found in registry"
            raise ServiceNotFound(msg) from err
        return func.implementation

    def get_metadata(
        self, service_key: ServiceKey, service_version: ServiceVersion
    ) -> ServiceMetaDataPublished:
        """raises ServiceNotFound"""
        try:
            func = self._functions[(service_key, service_version)]
        except KeyError as err:
            msg = f"{service_key}:{service_version} not found in registry"
            raise ServiceNotFound(msg) from err
        return func.meta

    def __len__(self):
        return len(self._functions)
