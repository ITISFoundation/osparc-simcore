import json
import os
from typing import Dict, Tuple
from urllib.parse import quote

from ..services import Author, ServiceDockerData

# Expects env var: FUNCTION_SERVICES_AUTHORS='{"OM":{"name": ...}, "EN":{...} }'
try:
    AUTHORS = json.loads(os.environ.get("FUNCTION_SERVICES_AUTHORS", "{}"))
except json.decoder.JSONDecodeError:
    AUTHORS = {}

_DEFAULT = {
    "name": "Unknown",
    "email": "unknown@osparc.io",
    "affiliation": "unknown",
}
EN = Author.parse_obj(AUTHORS.get("EN", _DEFAULT))
OM = Author.parse_obj(AUTHORS.get("OM", _DEFAULT))
PC = Author.parse_obj(AUTHORS.get("PC", _DEFAULT))


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
