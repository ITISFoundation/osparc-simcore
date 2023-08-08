# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

from typing import Any

import pytest
import respx
from faker import Faker
from fastapi import FastAPI
from models_library.services import ServiceKeyVersion
from models_library.users import UserID
from pytest import MonkeyPatch
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_director_v2.modules.catalog import CatalogClient


@pytest.fixture
def minimal_catalog_config(
    disable_postgres: None,
    project_env_devel_environment: EnvVarsDict,
    monkeypatch: MonkeyPatch,
) -> None:
    """set a minimal configuration for testing the director connection only"""
    monkeypatch.setenv("DIRECTOR_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V0_ENABLED", "0")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED", "0")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_ENABLED", "0")


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return UserID(faker.pyint(min_value=1))


def test_get_catalog_client_instance(
    minimal_catalog_config: None,
    mocked_catalog_service_api: respx.MockRouter,
    minimal_app: FastAPI,
):
    catalog_client: CatalogClient = minimal_app.state.catalog_client
    assert catalog_client
    assert CatalogClient.instance(minimal_app) == catalog_client


async def test_get_service_specifications(
    minimal_catalog_config: None,
    mocked_catalog_service_api: respx.MockRouter,
    minimal_app: FastAPI,
    user_id: UserID,
    mock_service_key_version: ServiceKeyVersion,
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
    assert "sidecar" in service_specifications
    assert service_specifications == fake_service_specifications
