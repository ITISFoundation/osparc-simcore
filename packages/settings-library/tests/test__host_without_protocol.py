# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import Mapping
from typing import Annotated, Final

import pytest
from annotated_types import doc
from pydantic import ValidationError
from settings_library.base import BaseCustomSettings
from settings_library.catalog import CatalogSettings
from settings_library.director_v0 import DirectorV0Settings
from settings_library.director_v2 import DirectorV2Settings
from settings_library.docker_api_proxy import DockerApiProxysettings
from settings_library.docker_registry import RegistrySettings
from settings_library.postgres import PostgresSettings
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from settings_library.resource_usage_tracker import ResourceUsageTrackerSettings
from settings_library.storage import StorageSettings
from settings_library.webserver import WebServerSettings

_HOST_FIELDS: Final[
    Annotated[
        list[tuple[type[BaseCustomSettings], str, Mapping[str, object]]],
        doc("settings class, hostname field, the other required fields"),
    ]
] = [
    (
        RegistrySettings,
        "REGISTRY_URL",
        {
            "REGISTRY_AUTH": False,
            "REGISTRY_USER": "usr",
            "REGISTRY_PW": "pwd",
            "REGISTRY_SSL": False,
        },
    ),
    (
        RegistrySettings,
        "REGISTRY_PATH",
        {
            "REGISTRY_AUTH": False,
            "REGISTRY_USER": "usr",
            "REGISTRY_PW": "pwd",
            "REGISTRY_SSL": False,
            "REGISTRY_URL": "registry.example.com",
        },
    ),
    (
        PostgresSettings,
        "POSTGRES_HOST",
        {"POSTGRES_USER": "usr", "POSTGRES_PASSWORD": "pwd", "POSTGRES_DB": "db"},
    ),
    (RedisSettings, "REDIS_HOST", {}),
    (
        RabbitSettings,
        "RABBIT_HOST",
        {"RABBIT_SECURE": False, "RABBIT_USER": "usr", "RABBIT_PASSWORD": "pwd"},
    ),
    (
        DockerApiProxysettings,
        "DOCKER_API_PROXY_HOST",
        {"DOCKER_API_PROXY_USER": "usr", "DOCKER_API_PROXY_PASSWORD": "pwd"},
    ),
    (WebServerSettings, "WEBSERVER_HOST", {}),
    (CatalogSettings, "CATALOG_HOST", {}),
    (StorageSettings, "STORAGE_HOST", {}),
    (DirectorV0Settings, "DIRECTOR_HOST", {}),
    (DirectorV2Settings, "DIRECTOR_V2_HOST", {}),
    (ResourceUsageTrackerSettings, "RESOURCE_USAGE_TRACKER_HOST", {}),
]

_IDS: Final[list[str]] = [f"{cls.__name__}.{field}" for cls, field, _ in _HOST_FIELDS]
_PROTOCOL_VALUES: Final[list[str]] = [
    "http://svc",
    "https://svc:8080",
    "HTTP://svc",
    "https://",  # protocol-only: still a scheme, must not survive trimming
    "HTTP://",
]


@pytest.mark.parametrize(
    "settings_cls,field,required",
    _HOST_FIELDS,
    ids=_IDS,
)
@pytest.mark.parametrize("bad_value", _PROTOCOL_VALUES)
def test_host_field_rejects_protocol(
    settings_cls: type[BaseCustomSettings],
    field: str,
    required: Mapping[str, object],
    bad_value: str,
):
    with pytest.raises(ValidationError, match="without protocol"):
        settings_cls.model_validate({**required, field: bad_value})


@pytest.mark.parametrize(
    "settings_cls,field,required",
    _HOST_FIELDS,
    ids=_IDS,
)
def test_host_field_accepts_hostname(
    settings_cls: type[BaseCustomSettings],
    field: str,
    required: Mapping[str, object],
):
    settings = settings_cls.model_validate({**required, field: "svc.local:5000"})
    assert getattr(settings, field) == "svc.local:5000"


def test_registry_url_trims_whitespace_and_trailing_slash():
    settings = RegistrySettings.model_validate(
        {
            "REGISTRY_AUTH": False,
            "REGISTRY_USER": "usr",
            "REGISTRY_PW": "pwd",
            "REGISTRY_SSL": True,
            "REGISTRY_URL": "  registry.example.com/ ",
        }
    )
    assert settings.REGISTRY_URL == "registry.example.com"
    assert str(settings.api_url) == "https://registry.example.com/v2"
