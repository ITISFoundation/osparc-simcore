# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

import pytest
from faker import Faker
from pytest_simcore.helpers.docker import get_service_published_port
from pytest_simcore.helpers.host import get_localhost_ip
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.s3 import S3Settings


@pytest.fixture
def minio_s3_settings(
    docker_stack: dict, testing_environ_vars: dict, faker: Faker
) -> S3Settings:
    assert "pytest-ops_minio" in docker_stack["services"]

    return S3Settings(
        S3_ACCESS_KEY=testing_environ_vars["S3_ACCESS_KEY"],
        S3_SECRET_KEY=testing_environ_vars["S3_SECRET_KEY"],
        S3_ENDPOINT=f"http://{get_localhost_ip()}:{get_service_published_port('minio')}",
        S3_BUCKET_NAME=testing_environ_vars["S3_BUCKET_NAME"],
        S3_REGION="us-east-1",
    )


@pytest.fixture
def minio_s3_settings_envs(
    minio_s3_settings: S3Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    changed_envs: EnvVarsDict = minio_s3_settings.dict(exclude_unset=True)
    return setenvs_from_dict(monkeypatch, changed_envs)
