import logging
from dataclasses import dataclass
from typing import Callable, Dict, Iterator, Optional, Tuple
from urllib.parse import quote

from ..services import Author, ServiceDockerData, ServiceKey, ServiceVersion
from ._settings import AUTHORS, FunctionServiceSettings

log = logging.getLogger(__name__)


_DEFAULT = {
    "name": "Unknown",
    "email": "unknown@osparc.io",
    "affiliation": "unknown",
}
EN = Author.parse_obj(AUTHORS.get("EN", _DEFAULT))
OM = Author.parse_obj(AUTHORS.get("OM", _DEFAULT))
PC = Author.parse_obj(AUTHORS.get("PC", _DEFAULT))


def create_fake_thumbnail_url(label: str) -> str:
    return f"https://fakeimg.pl/100x100/ff0000%2C128/000%2C255/?text={quote(label)}"


class ServiceNotFound(KeyError):
    pass


@dataclass
class _Record:
    meta: ServiceDockerData
    implementation: Optional[Callable] = None
    is_under_development: bool = False


class FunctionServices:
    """Used to register a collection of function services"""

    def __init__(self, settings: Optional[FunctionServiceSettings] = None):
        self._functions: Dict[Tuple[ServiceKey, ServiceVersion], _Record] = {}
        self.settings = settings

    def add(
        self,
        meta: ServiceDockerData,
        implementation: Optional[Callable] = None,
        is_under_development: bool = False,
    ):
        """
        raises ValueError
        """
        if not isinstance(meta, ServiceDockerData):
            raise ValueError(f"Expected ServiceDockerData, got {type(meta)}")

        # ensure unique
        if (meta.key, meta.version) in self._functions:
            raise ValueError(f"{(meta.key, meta.version)} is already registered")

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

    def _items(self) -> Iterator[Tuple[Tuple[ServiceKey, ServiceVersion], _Record]]:
        skip_dev = self._skip_dev()
        for key, value in self._functions.items():
            if value.is_under_development and skip_dev:
                continue
            yield key, value

    def iter_metadata(self) -> Iterator[ServiceDockerData]:
        for _, f in self._items():
            yield f.meta

    def iter_services_key_version(self) -> Iterator[Tuple[ServiceKey, ServiceVersion]]:
        for kv, f in self._items():
            assert kv == (f.meta.key, f.meta.version)  # nosec
            yield kv

    def get_implementation(
        self, service_key: ServiceKey, service_version: ServiceVersion
    ) -> Optional[Callable]:
        """raises ServiceNotFound"""
        try:
            func = self._functions[(service_key, service_version)]
        except KeyError as err:
            raise ServiceNotFound(
                f"{service_key}:{service_version} not found in registry"
            ) from err
        return func.implementation

    def get_metadata(
        self, service_key: ServiceKey, service_version: ServiceVersion
    ) -> ServiceDockerData:
        """raises ServiceNotFound"""
        try:
            func = self._functions[(service_key, service_version)]
        except KeyError as err:
            raise ServiceNotFound(
                f"{service_key}:{service_version} not found in registry"
            ) from err
        return func.meta

    def __len__(self):
        return len(self._functions)
