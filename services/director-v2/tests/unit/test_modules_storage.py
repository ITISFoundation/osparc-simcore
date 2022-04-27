# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

import pytest
import respx
from faker import Faker
from fastapi import FastAPI
from models_library.users import UserID
from settings_library.s3 import S3Settings
from simcore_service_director_v2.modules.storage import StorageClient


@pytest.fixture
def minimal_storage_config(project_env_devel_environment, monkeypatch):
    """set a minimal configuration for testing the director connection only"""
    ...
    # monkeypatch.setenv("DIRECTOR_ENABLED", "0")
    # monkeypatch.setenv("POSTGRES_ENABLED", "0")
    # monkeypatch.setenv("REGISTRY_ENABLED", "0")
    # monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "false")
    # monkeypatch.setenv("DIRECTOR_V0_ENABLED", "1")
    # monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "0")
    # monkeypatch.setenv("COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED", "0")
    # monkeypatch.setenv("COMPUTATIONAL_BACKEND_ENABLED", "0")


@pytest.fixture
def fake_s3_settings(faker: Faker) -> S3Settings:
    return S3Settings(
        S3_ENDPOINT=faker.uri(),
        S3_ACCESS_KEY=faker.uuid4(),
        S3_SECRET_KEY=faker.uuid4(),
        S3_ACCESS_TOKEN=faker.uuid4(),
        S3_BUCKET_NAME=faker.pystr(),
    )


@pytest.fixture
def mocked_storage_service_fcts(minimal_app: FastAPI, fake_s3_settings):
    with respx.mock(
        base_url=minimal_app.state.settings.DIRECTOR_V2_STORAGE.endpoint,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:

        respx_mock.post(
            f"/simcore-s3:access",
            name="get_or_create_temporary_s3_access",
        ).respond(json={"data": [fake_s3_settings.dict(by_alias=True)]})

        yield respx_mock


async def test_get_simcore_s3_access(
    minimal_storage_config: None,
    minimal_app: FastAPI,
    mocked_storage_service_fcts,
    user_id: UserID,
    fake_s3_settings: S3Settings,
):
    storage_client: StorageClient = minimal_app.state.storage_v0_client
    simcore_s3_settings: S3Settings = await storage_client.get_s3_access(user_id)

    assert mocked_storage_service_fcts["get_or_create_temporary_s3_access"].called
    assert fake_s3_settings == simcore_s3_settings
