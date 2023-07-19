# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.users import UserID
from settings_library.s3 import S3Settings
from simcore_service_director_v2.modules.storage import StorageClient


@pytest.fixture
def minimal_storage_config(project_env_devel_environment, monkeypatch):
    """set a minimal configuration for testing the director connection only"""
    monkeypatch.setenv("DIRECTOR_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V0_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_CATALOG", "null")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED", "0")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_ENABLED", "0")


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return UserID(faker.pyint(min_value=1))


def test_get_storage_client_instance(
    minimal_storage_config: None,
    minimal_app: FastAPI,
):
    storage_client: StorageClient = minimal_app.state.storage_client
    assert storage_client
    assert StorageClient.instance(minimal_app) == storage_client


async def test_get_simcore_s3_access(
    minimal_storage_config: None,
    minimal_app: FastAPI,
    mocked_storage_service_api,
    user_id: UserID,
    fake_s3_settings: S3Settings,
):
    storage_client: StorageClient = minimal_app.state.storage_client
    assert storage_client
    simcore_s3_settings: S3Settings = await storage_client.get_s3_access(user_id)

    assert mocked_storage_service_api["get_or_create_temporary_s3_access"].called
    assert fake_s3_settings == simcore_s3_settings
