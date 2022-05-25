# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from pytest import MonkeyPatch
from simcore_service_image_puller.settings import ImagePullerSettings


@pytest.fixture(params=["HOSTNAME", "IMAGE_PULLER_CHECK_HOSTNAME"])
def hostname_env_vars(request) -> str:
    return request.param


@pytest.fixture
def hostname() -> str:
    return "test-host"


@pytest.fixture
def mocked_env(monkeypatch: MonkeyPatch, hostname_env_vars: str, hostname: str) -> None:
    monkeypatch.setenv(hostname_env_vars, hostname)


@pytest.fixture
def settings(mocked_env: None) -> ImagePullerSettings:
    return ImagePullerSettings.create_from_envs()
