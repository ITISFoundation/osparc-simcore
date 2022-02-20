from typing import Dict, Final, Tuple
from urllib.parse import quote

from ..services import ServiceDockerData

FRONTEND_SERVICE_KEY_PREFIX: Final[str] = "simcore/services/frontend"

EN: Dict[str, str] = {
    "name": "Esra Neufeld",
    "email": "neufeld@itis.swiss",
    "affiliation": "IT'IS",
}
OM: Dict[str, str] = {
    "name": "Odei Maiz",
    "email": "maiz@itis.swiss",
    "affiliation": "IT'IS",
}
# TODO: how to avoid explicit names here to define ownership?
#


_NodeKeyVersionPair = Tuple[str, str]


def create_fake_thumbnail_url(label: str) -> str:
    return f"https://fakeimg.pl/100x100/ff0000%2C128/000%2C255/?text={quote(label)}"


def register(
    *meta_objects: ServiceDockerData,
) -> Dict[_NodeKeyVersionPair, ServiceDockerData]:
    """Used to do a first validation and dump data in an intermediate trusted registry"""
    _validated_registry = {}
    for meta in meta_objects:
        if not isinstance(meta, ServiceDockerData):
            raise ValueError(f"Expected ServiceDockerData, got {type(meta)}")

        kv = (meta.key, meta.version)
        if kv in _validated_registry:
            raise ValueError(f"{(meta.key, meta.version)=} is already registered")

        _validated_registry[kv] = meta
    return _validated_registry
