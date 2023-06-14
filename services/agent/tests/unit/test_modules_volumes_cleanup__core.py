# pylint:disable=redefined-outer-name


import itertools
import tarfile
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from shutil import copy
from typing import AsyncIterable, Final
from unittest.mock import call
from uuid import UUID, uuid4

import aiodocker
import pytest
from aiodocker import Docker
from aiodocker.containers import DockerContainer
from aiodocker.volumes import DockerVolume
from faker import Faker
from models_library.sidecar_volumes import VolumeCategory, VolumeState, VolumeStatus
from pydantic import BaseModel, NonNegativeInt
from pytest_mock import MockerFixture
from servicelib.sidecar_volumes import STORE_FILE_NAME, VolumeUtils
from simcore_service_agent.core.settings import ApplicationSettings
from simcore_service_agent.modules.volumes_cleanup._core import (
    SHARED_STORE_PATH,
    SidecarVolumes,
    _get_volumes_status,
    backup_and_remove_sidecar_volumes,
    get_sidecar_volumes_list,
)
from simcore_service_agent.modules.volumes_cleanup.models import VolumeDict

_VOLUMES_TO_GENERATE: Final[NonNegativeInt] = 10


def _get_minimal_volume_dict(node_uuid: str, run_id: str, path: Path) -> VolumeDict:
    # NOTE: minimal fields are added for the purpose of the tests
    return {
        "Name": VolumeUtils.get_source(path, UUID(node_uuid), UUID(run_id)),
    }


def _get_fake_sidecar_volumes(faker: Faker) -> list[VolumeDict]:
    node_uuid = faker.uuid4()
    run_id = faker.uuid4()
    return [
        _get_minimal_volume_dict(node_uuid, run_id, Path(f"/tmp/dir{x}"))
        for x in range(_VOLUMES_TO_GENERATE)
    ] + [
        _get_minimal_volume_dict(node_uuid, run_id, SHARED_STORE_PATH),
    ]


@pytest.mark.parametrize("sidecar_count", [0, 1, 9])
def test__get_sidecar_volumes_list(faker: Faker, sidecar_count: int):
    mix_of_volumes: list[VolumeDict] = list(
        itertools.chain.from_iterable(
            _get_fake_sidecar_volumes(faker) for x in range(sidecar_count)
        )
    )
    assert len(mix_of_volumes) == sidecar_count * (_VOLUMES_TO_GENERATE + 1)

    shared_volumes_list: list[SidecarVolumes] = get_sidecar_volumes_list(mix_of_volumes)

    assert len(shared_volumes_list) == sidecar_count
    for shared_volumes in shared_volumes_list:
        assert shared_volumes.store_volume
        assert len(shared_volumes.remaining_volumes) == _VOLUMES_TO_GENERATE
        assert shared_volumes.store_volume["Name"] not in {
            x["Name"] for x in shared_volumes.remaining_volumes
        }


def test_sidecar_volumes_from_volumes(faker: Faker):
    volumes: list[VolumeDict] = _get_fake_sidecar_volumes(faker)
    assert SidecarVolumes.from_volumes(volumes)

    volumes.pop()  # removes last element containing the data volume
    with pytest.raises(ValueError, match=r"store_volume"):
        SidecarVolumes.from_volumes(volumes)


@pytest.fixture
async def fake_legacy_data_volume_dict(
    unused_volume: DockerVolume,
    tmp_path: Path,
    legacy_shared_store_only_volume_states: Path,
) -> AsyncIterable[VolumeDict]:
    volume_data: VolumeDict = await unused_volume.show()

    # can't access directly docker's storage mocking destination
    volume_data["Mountpoint"] = f"{tmp_path}"
    shared_store_path = Path(volume_data["Mountpoint"]) / STORE_FILE_NAME

    copy(legacy_shared_store_only_volume_states, shared_store_path)
    assert shared_store_path.exists()

    yield volume_data
    shared_store_path.unlink()


async def test_get_volumes_status_legacy_format(
    fake_legacy_data_volume_dict: VolumeDict,
):
    # NOTE: if this test fails the agent is no longer capable
    # of parsing the existing format of the file
    # Please add a migration to support this format
    volumes_status: dict[str, VolumeStatus] = await _get_volumes_status(
        fake_legacy_data_volume_dict
    )
    assert volumes_status


@contextmanager
def _make_tarfile(
    archive_destination: Path,
    path_in_archive: Path,
    source_dir: Path,
) -> None:
    with tarfile.open(archive_destination, "w:gz") as tar:
        tar.add(source_dir, arcname=path_in_archive)
    try:
        yield
    finally:
        archive_destination.unlink()


async def _create_volume(
    volume_name: str,
    volume_path_in_container: Path | None = None,
    dir_to_copy: Path | None = None,
) -> VolumeDict:
    """
    creates a docker volume and copies the content of `dir_to_copy`  if not None
    """

    async with Docker() as client:
        volume: DockerVolume = await client.volumes.create({"Name": volume_name})

        if dir_to_copy:
            assert volume_path_in_container is not None
            container: DockerContainer = await client.containers.create(
                {
                    "Image": "busybox",
                    "HostConfig": {
                        "Binds": [f"{volume_name}:{volume_path_in_container}"]
                    },
                }
            )

            try:
                archive_path = Path(f"/tmp/tar_archive{uuid4()}")
                with _make_tarfile(archive_path, volume_path_in_container, dir_to_copy):

                    await container.put_archive(
                        f"{volume_path_in_container}", archive_path.read_bytes()
                    )
                    print("me")
            finally:
                await container.delete()

        volume_dict: VolumeDict = await volume.show()
        return volume_dict


# fixtures to create the volumes form the names and then put some data in one of these volumes


@pytest.fixture
async def volume_cleanup() -> list[str]:
    volumes_to_remove: list[str] = []
    yield volumes_to_remove

    async with Docker() as client:
        for volume_name in volumes_to_remove:
            docker_volume = DockerVolume(client, volume_name)
            try:
                await docker_volume.delete()
            except aiodocker.DockerError as e:
                assert e.status == 404


@pytest.fixture
async def sidecar_volumes(faker: Faker) -> SidecarVolumes:
    node_uuid = faker.uuid4()
    run_id = faker.uuid4()

    store_volume: VolumeDict = _get_minimal_volume_dict(
        node_uuid, run_id, SHARED_STORE_PATH
    )
    remaining_volumes: list[VolumeDict] = [
        _get_minimal_volume_dict(node_uuid, run_id, Path(f"/tmp/other-volumes-{x}"))
        for x in range(_VOLUMES_TO_GENERATE)
    ]

    return SidecarVolumes(
        store_volume=store_volume, remaining_volumes=remaining_volumes
    )


class _ParsingModel(BaseModel):
    volume_states: dict[VolumeCategory, VolumeState]


@pytest.fixture
def volume_states(sidecar_volumes: SidecarVolumes) -> dict[VolumeCategory, VolumeState]:
    # make a copy locally since pop will affect original dataset
    sidecar_volumes = deepcopy(sidecar_volumes)

    volume_states: dict[VolumeCategory, VolumeState] = {}

    # we have at least 1 volume for inputs outputs and states
    # all extra volumes will be put to states
    assert len(sidecar_volumes.remaining_volumes) >= 3

    inputs_volume = sidecar_volumes.remaining_volumes.pop()
    volume_states[VolumeCategory.INPUTS] = VolumeState(
        status=VolumeStatus.CONTENT_NO_SAVE_REQUIRED,
        volume_names=[inputs_volume["Name"]],
    )
    outputs_volume = sidecar_volumes.remaining_volumes.pop()
    volume_states[VolumeCategory.OUTPUTS] = VolumeState(
        status=VolumeStatus.CONTENT_NEEDS_TO_BE_SAVED,
        volume_names=[outputs_volume["Name"]],
    )
    assert len(sidecar_volumes.remaining_volumes) > 0
    state_volume_names: list[str] = []
    for state_volume_name in sidecar_volumes.remaining_volumes:
        state_volume_names.append(state_volume_name["Name"])

    assert inputs_volume not in state_volume_names
    assert outputs_volume not in state_volume_names

    volume_states[VolumeCategory.STATES] = VolumeState(
        status=VolumeStatus.CONTENT_NEEDS_TO_BE_SAVED, volume_names=state_volume_names
    )

    volume_states[VolumeCategory.SHARED_STORE] = VolumeState(
        status=VolumeStatus.CONTENT_NO_SAVE_REQUIRED,
        volume_names=[sidecar_volumes.store_volume["Name"]],
    )

    return volume_states


@pytest.fixture
def fake_shared_store_file(
    tmp_path: Path, volume_states: dict[VolumeCategory, VolumeState]
) -> Path:
    file_with_data = tmp_path / STORE_FILE_NAME
    # write format to file
    file_with_data.write_text(_ParsingModel(volume_states=volume_states).json())

    return file_with_data


@pytest.fixture
async def create_volumes(
    fake_shared_store_file: Path,
    sidecar_volumes: SidecarVolumes,
    volume_cleanup: list[str],
) -> SidecarVolumes:
    store_volume = sidecar_volumes.store_volume["Name"]

    # only one volume has a file inside it the one store
    created_store_volume: VolumeDict = await _create_volume(
        store_volume,
        volume_path_in_container=SHARED_STORE_PATH / STORE_FILE_NAME,
        dir_to_copy=fake_shared_store_file,
    )
    created_store_volume["Mountpoint"] = f"{fake_shared_store_file.parent}"
    volume_cleanup.append(store_volume)

    created_remaining_volumes: list[VolumeDict] = []

    for volume in sidecar_volumes.remaining_volumes:
        volume_name = volume["Name"]
        created_remaining_volumes.append(await _create_volume(volume_name))
        volume_cleanup.append(store_volume)

    return SidecarVolumes(
        store_volume=created_store_volume, remaining_volumes=created_remaining_volumes
    )


async def test_backup_and_remove_sidecar_volumes(
    mocker: MockerFixture,
    settings: ApplicationSettings,
    create_volumes: SidecarVolumes,
    volume_states: dict[VolumeCategory, VolumeState],
):
    mock_store_to_s3 = mocker.patch(
        "simcore_service_agent.modules.volumes_cleanup._core.store_to_s3"
    )

    await backup_and_remove_sidecar_volumes(settings, create_volumes)

    expected_calls: list[call] = []

    create_volumes_mapping: dict[str, VolumeDict] = {
        x["Name"]: x for x in create_volumes.remaining_volumes
    }

    for category, volume_state in volume_states.items():
        if category in (VolumeCategory.OUTPUTS, VolumeCategory.STATES):
            assert volume_state.status == VolumeStatus.CONTENT_NEEDS_TO_BE_SAVED
            for volume_name in volume_state.volume_names:
                expected_calls.append(
                    call(
                        volume_name=volume_name,
                        dyv_volume=create_volumes_mapping[volume_name],
                        s3_endpoint=settings.AGENT_VOLUMES_CLEANUP_S3_ENDPOINT,
                        s3_access_key=settings.AGENT_VOLUMES_CLEANUP_S3_ACCESS_KEY,
                        s3_secret_key=settings.AGENT_VOLUMES_CLEANUP_S3_SECRET_KEY,
                        s3_bucket=settings.AGENT_VOLUMES_CLEANUP_S3_BUCKET,
                        s3_region=settings.AGENT_VOLUMES_CLEANUP_S3_REGION,
                        s3_provider=settings.AGENT_VOLUMES_CLEANUP_S3_PROVIDER,
                        s3_retries=settings.AGENT_VOLUMES_CLEANUP_RETRIES,
                        s3_parallelism=settings.AGENT_VOLUMES_CLEANUP_PARALLELISM,
                        exclude_files=settings.AGENT_VOLUMES_CLEANUP_EXCLUDE_FILES,
                    )
                )
        else:
            assert volume_state.status in [
                VolumeStatus.CONTENT_NO_SAVE_REQUIRED,
                VolumeStatus.CONTENT_WAS_SAVED,
            ]

    mock_store_to_s3.assert_has_calls(expected_calls, any_order=True)
    # out of the _VOLUMES_TO_GENERATE one is used for inputs and does not require backup
    assert len(expected_calls) == _VOLUMES_TO_GENERATE - 1
