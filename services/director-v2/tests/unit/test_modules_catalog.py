# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

import urllib.parse
from typing import Any, Iterator

import pytest
import respx
from faker import Faker
from fastapi import FastAPI
from models_library.services import ServiceKeyVersion
from models_library.users import UserID
from simcore_service_director_v2.modules.catalog import CatalogClient


@pytest.fixture
def minimal_catalog_config(project_env_devel_environment, monkeypatch):
    """set a minimal configuration for testing the director connection only"""
    monkeypatch.setenv("DIRECTOR_ENABLED", "0")
    monkeypatch.setenv("POSTGRES_ENABLED", "0")
    monkeypatch.setenv("REGISTRY_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V0_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "0")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED", "0")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_ENABLED", "0")


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return UserID(faker.pyint(min_value=1))


def test_get_catalog_client_instance(
    minimal_catalog_config: None,
    minimal_app: FastAPI,
):
    catalog_client: CatalogClient = minimal_app.state.catalog_client
    assert catalog_client
    assert CatalogClient.instance(minimal_app) == catalog_client


@pytest.fixture
def mock_service_key_version() -> ServiceKeyVersion:
    return ServiceKeyVersion(key="simcore/services/dynamic/myservice", version="1.4.5")


@pytest.fixture
def fake_service_specifications(faker: Faker) -> dict[str, Any]:
    # the service specifications follow the Docker service creation available
    # https://docs.docker.com/engine/api/v1.41/#operation/ServiceCreate
    return {
        "schedule_specs": {
            "Labels": {"label_one": faker.pystr(), "label_two": faker.pystr()},
            "TaskTemplate": {
                "Placement": {
                    "Constraints": [
                        "node.id==2ivku8v2gvtg4",
                        "node.hostname!=node-2",
                        "node.platform.os==linux",
                        "node.labels.security==high",
                        "engine.labels.operatingsystem==ubuntu-20.04",
                    ]
                },
                "Resources": {
                    "Limits": {"NanoCPUs": 16 * 10e9, "MemoryBytes": 10 * 1024**3},
                    "Reservation": {
                        "NanoCPUs": 1 * 10e9,
                        "MemoryBytes": 1 * 1024**3,
                        "GenericResources": [
                            {
                                "NamedResourceSpec": {
                                    "Kind": "Chipset",
                                    "Value": "Late2020",
                                }
                            },
                            {
                                "DiscreteResourceSpec": {
                                    "Kind": "VRAM",
                                    "Value": 1 * 1024**3,
                                }
                            },
                        ],
                    },
                },
                "ContainerSpec": {
                    "Command": ["my", "super", "duper", "service", "command"],
                    "Env": {"SOME_FAKE_ADDITIONAL_ENV": faker.pystr().upper()},
                },
            },
        }
    }


@pytest.fixture
def mocked_catalog_service_fcts(
    minimal_app: FastAPI,
    mock_service_key_version: ServiceKeyVersion,
    fake_service_specifications: dict[str, Any],
) -> Iterator[respx.MockRouter]:
    with respx.mock(
        base_url=minimal_app.state.settings.DIRECTOR_V2_CATALOG.endpoint,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        quoted_key = urllib.parse.quote(mock_service_key_version.key, safe="")
        version = mock_service_key_version.version
        respx_mock.get(
            f"/services/{quoted_key}/{version}/specifications",
            name="get_service_specifications",
        ).respond(json=fake_service_specifications)

        yield respx_mock


async def test_get_service_specifications(
    minimal_catalog_config: None,
    minimal_app: FastAPI,
    user_id: UserID,
    mock_service_key_version: ServiceKeyVersion,
    mocked_catalog_service_fcts: respx.MockRouter,
    fake_service_specifications: dict[str, Any],
):
    catalog_client: CatalogClient = minimal_app.state.catalog_client
    assert catalog_client
    service_specifications: dict[
        str, Any
    ] = await catalog_client.get_service_specifications(
        user_id, mock_service_key_version.key, mock_service_key_version.version
    )
    assert service_specifications
    assert "schedule_specs" in service_specifications
    assert service_specifications == fake_service_specifications
