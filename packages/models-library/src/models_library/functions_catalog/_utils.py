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


NameVersionPair = Tuple[str, str]


def get_fake_thumbnail(label) -> str:
    return f"https://fakeimg.pl/100x100/ff0000%2C128/000%2C255/?text={quote(label)}"


def register(
    *meta_objects: ServiceDockerData,
) -> Dict[NameVersionPair, ServiceDockerData]:
    """Used to do a first validation and dump data in an intermediate trusted registry"""
    _validated_registry = {}
    for meta in meta_objects:
        if not isinstance(meta, ServiceDockerData):
            raise ValueError(f"Expected ServiceDockerData, got {type(meta)}")

        key = (meta.name, meta.version)
        if key in _validated_registry:
            raise ValueError(f"{key} is already registered")

        _validated_registry[key] = meta
    return _validated_registry
