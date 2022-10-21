# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


from pathlib import Path

import pytest
from aiodocker.volumes import DockerVolume
from pytest import CaptureFixture, MonkeyPatch
from pytest_mock.plugin import MockerFixture
from settings_library.r_clone import S3Provider
from simcore_service_simcore_agent.settings import ApplicationSettings
from simcore_service_simcore_agent.volumes_cleanup import backup_and_remove_volumes


@pytest.fixture
async def mock_volumes_folders(
    mocker: MockerFixture,
    unused_volume: DockerVolume,
    used_volume: DockerVolume,
    unused_volume_path: Path,
    used_volume_path: Path,
) -> None:
    # overwrite to test locally not against volume
    # root permissions are required to access this
    # only returning the volumes which are interesting

    unused_volume_path.mkdir(parents=True, exist_ok=True)
    used_volume_path.mkdir(parents=True, exist_ok=True)

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
def env(monkeypatch: MonkeyPatch, minio: dict, bucket: str) -> None:
    mock_dict = {
        "S3_ENDPOINT": minio["endpoint"],
        "S3_ACCESS_KEY": minio["access_key"],
        "S3_SECRET_KEY": minio["secret_key"],
        "S3_BUCKET": bucket,
        "S3_PROVIDER": S3Provider.MINIO,
    }
    for key, value in mock_dict.items():
        monkeypatch.setenv(key, value)


async def test_workflow(
    mock_volumes_folders: None,
    capsys: CaptureFixture,
    settings: ApplicationSettings,
    used_volume_name: str,
    unused_volume_name: str,
):
    await backup_and_remove_volumes(settings)

    stdout, stderr = capsys.readouterr()
    assert f"Removed docker volume: '{unused_volume_name}'" in stdout
    assert f"Skipped in use docker volume: '{used_volume_name}'" in stdout
    assert stderr == "", stderr
