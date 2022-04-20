# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

from pathlib import Path

import pytest
from _pytest.logging import LogCaptureFixture
from faker import Faker
from pytest import MonkeyPatch
from settings_library.r_clone import S3Provider
from simcore_sdk.node_ports_v2 import r_clone
from simcore_sdk.node_ports_v2.r_clone import RCloneSettings


@pytest.fixture
def text_to_write(faker: Faker) -> str:
    return faker.text()


@pytest.fixture(params=list(S3Provider))
def s3_provider(request) -> S3Provider:
    return request.param


@pytest.fixture
def r_clone_settings(
    monkeypatch: MonkeyPatch, s3_provider: S3Provider
) -> RCloneSettings:
    monkeypatch.setenv("R_CLONE_PROVIDER", s3_provider.value)
    monkeypatch.setenv("S3_ENDPOINT", "endpoint")
    monkeypatch.setenv("S3_ACCESS_KEY", "access_key")
    monkeypatch.setenv("S3_SECRET_KEY", "secret_key")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket_name")
    monkeypatch.setenv("S3_SECURE", "false")
    return RCloneSettings()


async def test_is_r_clone_installed_cached(
    caplog: LogCaptureFixture, r_clone_settings: RCloneSettings
) -> None:
    for _ in range(3):
        result = await r_clone.is_r_clone_installed(r_clone_settings)
        assert type(result) is bool
    assert "'rclone --version' result:\n" in caplog.text
    assert caplog.text.count("'rclone --version' result:\n") == 1

    assert await r_clone.is_r_clone_installed(None) is False


async def test__config_file(text_to_write: str) -> None:
    async with r_clone._config_file(text_to_write) as file_name:
        assert text_to_write == Path(file_name).read_text()
    assert Path(file_name).exists() is False


async def test__async_command_ok() -> None:
    await r_clone._async_command(" ".join(["ls", "-la"]))


async def test__async_command_error() -> None:
    with pytest.raises(r_clone._CommandFailedException):
        await r_clone._async_command("__i_do_not_exist__")
