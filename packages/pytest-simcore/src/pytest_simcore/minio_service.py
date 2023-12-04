# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

import pytest
from faker import Faker
from pydantic import parse_obj_as
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_docker import get_service_published_port
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from pytest_simcore.helpers.utils_host import get_localhost_ip
from settings_library.s3 import S3Settings


@pytest.fixture
def minio_s3_settings(
    docker_stack: dict, testing_environ_vars: dict, faker: Faker
) -> S3Settings:
    assert "pytest-ops_minio" in docker_stack["services"]

    return S3Settings(
        S3_ACCESS_KEY=testing_environ_vars["S3_ACCESS_KEY"],
        S3_SECRET_KEY=testing_environ_vars["S3_SECRET_KEY"],
        S3_ENDPOINT=f"{get_localhost_ip()}:{get_service_published_port('minio')}",
        S3_SECURE=parse_obj_as(bool, testing_environ_vars["S3_SECURE"]),
        S3_BUCKET_NAME=testing_environ_vars["S3_BUCKET_NAME"],
    )


@pytest.fixture
def minio_s3_settings_envs(
    minio_s3_settings: S3Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    changed_envs: EnvVarsDict = minio_s3_settings.dict(exclude_unset=True)
    return setenvs_from_dict(monkeypatch, changed_envs)
