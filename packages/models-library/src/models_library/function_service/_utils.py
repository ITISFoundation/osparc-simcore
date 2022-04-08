import json
import logging
import os
from typing import Dict, Final, Tuple
from urllib.parse import quote

from pydantic import BaseSettings

from ..services import Author, ServiceDockerData

log = logging.getLogger(__name__)

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


class FunctionServiceSettings(BaseSettings):
    CATALOG_DEV_FEATURES_ENABLED: bool = False
    DIRECTOR_V2_DEV_FEATURES_ENABLED: bool = False
    WEBSERVER_DEV_FEATURES_ENABLED: bool = False

    def is_dev_feature_enabled(self) -> bool:
        # NOTE that this is imported in these services
        # This solution is not ideal but will suffice
        # until function-services are moved to the database
        return (
            self.CATALOG_DEV_FEATURES_ENABLED
            or self.DIRECTOR_V2_DEV_FEATURES_ENABLED
            or self.WEBSERVER_DEV_FEATURES_ENABLED
        )


SETTINGS: Final[FunctionServiceSettings] = FunctionServiceSettings()


def create_fake_thumbnail_url(label: str) -> str:
    return f"https://fakeimg.pl/100x100/ff0000%2C128/000%2C255/?text={quote(label)}"


def register(
    *meta_objects: ServiceDockerData, is_development_feature: bool = False
) -> Dict[_NodeKeyVersionPair, ServiceDockerData]:
    """Used to do a first validation and dump data in an intermediate trusted registry"""
    _validated_registry = {}
    for meta in meta_objects:
        if not isinstance(meta, ServiceDockerData):
            raise ValueError(f"Expected ServiceDockerData, got {type(meta)}")

        if is_development_feature and not SETTINGS.is_dev_feature_enabled():
            log.debug(
                "Skipping function-service %s from catalong since dev features are disabled",
                f"{meta}",
            )
            continue

        kv = (meta.key, meta.version)
        if kv in _validated_registry:
            raise ValueError(f"{(meta.key, meta.version)} is already registered")

        _validated_registry[kv] = meta
    return _validated_registry
