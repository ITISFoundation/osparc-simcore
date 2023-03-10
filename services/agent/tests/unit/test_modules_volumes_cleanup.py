# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


from pathlib import Path
from typing import AsyncIterator

import pytest
from aiodocker.volumes import DockerVolume
from fastapi import FastAPI
from pytest import LogCaptureFixture
from pytest_mock.plugin import MockerFixture
from simcore_service_agent.core.settings import ApplicationSettings
from simcore_service_agent.modules import low_priority_managers
from simcore_service_agent.modules.volumes_cleanup import backup_and_remove_volumes

# FIXTURES


@pytest.fixture
async def mock_volumes_folders(
    mocker: MockerFixture,
    unused_volume: DockerVolume,
    used_volume: DockerVolume,
    unused_volume_path: Path,
    used_volume_path: Path,
) -> None:

    unused_volume_path.mkdir(parents=True, exist_ok=True)
    used_volume_path.mkdir(parents=True, exist_ok=True)

    # root permissions are required to access the /var/docker data
    # overwriting with a mocked path for this test
    unused_volume_data = await unused_volume.show()
    unused_volume_data["Mountpoint"] = f"{unused_volume_path}"
    used_volume_data = await used_volume.show()
    used_volume_data["Mountpoint"] = f"{used_volume_path}"

    volumes_inspect = [unused_volume_data, used_volume_data]

    # patch the function here
    mocker.patch(
        "aiodocker.volumes.DockerVolumes.list",
        return_value={"Volumes": volumes_inspect},
    )


@pytest.fixture
async def used_volume_name(used_volume: DockerVolume) -> str:
    return (await used_volume.show())["Name"]


@pytest.fixture
async def unused_volume_name(unused_volume: DockerVolume) -> str:
    return (await unused_volume.show())["Name"]


@pytest.fixture
async def app(settings: ApplicationSettings) -> AsyncIterator[FastAPI]:
    app = FastAPI()
    app.state.settings = settings
    low_priority_managers.setup(app)

    await app.router.startup()
    yield app
    await app.router.shutdown()


# TESTS


async def test_workflow(
    mock_volumes_folders: None,
    app: FastAPI,
    caplog_info_debug: LogCaptureFixture,
    used_volume_name: str,
    unused_volume_name: str,
):
    await backup_and_remove_volumes(app)

    log_messages = caplog_info_debug.messages
    assert f"Removed docker volume: '{unused_volume_name}'" in log_messages
    assert f"Skipped in use docker volume: '{used_volume_name}'" in log_messages


@pytest.mark.parametrize(
    "error_class, error_message",
    [
        (RuntimeError, "this was already handled"),
        (Exception, "also capture all other generic errors"),
    ],
)
async def test_regression_error_handling(
    mock_volumes_folders: None,
    caplog_info_debug: LogCaptureFixture,
    app: FastAPI,
    used_volume_name: str,
    unused_volume_name: str,
    mocker: MockerFixture,
    error_class: type[BaseException],
    error_message: str,
):
    mocker.patch(
        "simcore_service_agent.modules.volumes_cleanup._core.store_to_s3",
        side_effect=error_class(error_message),
    )

    await backup_and_remove_volumes(app)

    log_messages = caplog_info_debug.messages
    assert error_message in log_messages
