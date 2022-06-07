# pylint: disable=redefined-outer-name
# pylint: disable=protected-access
# pylint: disable=unused-argument

import subprocess
from pathlib import Path
from typing import Iterable, List, Optional
from unittest.mock import Mock

import pytest
from pytest_mock.plugin import MockerFixture
from faker import Faker
from pytest import MonkeyPatch
from settings_library.r_clone import S3Provider
from simcore_sdk.node_ports_common import r_clone
from simcore_sdk.node_ports_common.r_clone import RCloneSettings


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


@pytest.fixture
def skip_if_r_clone_is_missing() -> None:
    try:
        subprocess.check_output(["rclone", "--version"])
    except Exception:  # pylint: disable=broad-except
        pytest.skip("rclone is not installed")


@pytest.fixture
def mock_async_command(mocker: MockerFixture) -> Iterable[Mock]:
    mock = Mock()

    original_async_command = r_clone._async_command

    async def _mock_async_command(*cmd: str, cwd: Optional[str] = None) -> str:
        mock()
        return await original_async_command(*cmd, cwd=cwd)

    mocker.patch(
        "simcore_sdk.node_ports_common.r_clone._async_command",
        side_effect=_mock_async_command,
    )

    yield mock


async def test__config_file(faker: Faker) -> None:
    text_to_write = faker.text()
    async with r_clone._config_file(text_to_write) as file_name:
        assert text_to_write == Path(file_name).read_text()
    assert Path(file_name).exists() is False


async def test__async_command_ok() -> None:
    await r_clone._async_command("ls", "-la")


@pytest.mark.parametrize(
    "cmd",
    [
        ("__i_do_not_exist__",),
        ("ls_", "-lah"),
    ],
)
async def test__async_command_error(cmd: List[str]) -> None:
    with pytest.raises(r_clone._CommandFailedException) as exe_info:
        await r_clone._async_command(*cmd)
    assert (
        f"{exe_info.value}"
        == f"Command {' '.join(cmd)} finished with exception:\n/bin/sh: 1: {cmd[0]}: not found\n"
    )
