# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

import pytest
from common_library.serialization import model_dump_with_secrets
from faker import Faker
from pydantic import AnyHttpUrl, SecretStr, TypeAdapter
from settings_library.s3 import S3Settings

from pytest_simcore.helpers.docker import get_service_published_port
from pytest_simcore.helpers.host import get_localhost_ip
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.xdist import get_worker_id


@pytest.fixture
def s3_storage_settings(
    docker_stack: dict, env_vars_for_docker_compose: EnvVarsDict, faker: Faker, request: pytest.FixtureRequest
) -> S3Settings:
    assert "pytest-ops_s3-storage" in docker_stack["services"]

    # under xdist, each worker gets its own bucket on the SAME shared S3/rustfs container
    bucket_name = env_vars_for_docker_compose["S3_BUCKET_NAME"]
    worker_id = get_worker_id(request)
    if worker_id != "master":
        bucket_name = f"{bucket_name}_{worker_id}"

    return S3Settings(
        S3_ACCESS_KEY=SecretStr(env_vars_for_docker_compose["S3_ACCESS_KEY"]),
        S3_SECRET_KEY=SecretStr(env_vars_for_docker_compose["S3_SECRET_KEY"]),
        S3_ENDPOINT=TypeAdapter(AnyHttpUrl).validate_python(
            f"http://{get_localhost_ip()}:{get_service_published_port('s3-storage')}"
        ),
        S3_BUCKET_NAME=bucket_name,
        S3_REGION="us-east-1",
    )


@pytest.fixture
def s3_storage_settings_envs(
    s3_storage_settings: S3Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    changed_envs: EnvVarsDict = model_dump_with_secrets(
        s3_storage_settings,
        show_secrets=True,
    )

    return setenvs_from_dict(monkeypatch, changed_envs)
