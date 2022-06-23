# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import os
from pathlib import Path

import pytest
from aiodocker.volumes import DockerVolume
from fastapi import FastAPI
from simcore_service_dynamic_sidecar.core.application import AppState
from simcore_service_dynamic_sidecar.core.settings import DynamicSidecarSettings
from simcore_service_dynamic_sidecar.modules.mounted_fs import MountedVolumes


@pytest.fixture
def settings(app: FastAPI) -> DynamicSidecarSettings:
    return AppState(app).settings


def test_location_on_disk(
    mounted_volumes: MountedVolumes, settings: DynamicSidecarSettings
):
    # check location on disk
    assert all(p.exists() for p in mounted_volumes.disk_state_paths)

    assert all(p.exists() and p.is_dir() for p in mounted_volumes.all_disk_paths)

    assert all(
        settings.DYNAMIC_SIDECAR_DY_VOLUMES_COMMON_DIR in p.parents
        for p in mounted_volumes.all_disk_paths
    )


def test_volume_name_mount_point(
    mounted_volumes: MountedVolumes, compose_namespace: str
):
    # check volume mount point
    volume_names = [
        mounted_volumes.volume_name_outputs,
        mounted_volumes.volume_name_inputs,
    ] + mounted_volumes.volume_names_for_states

    assert all(
        volume_name.startswith(compose_namespace) for volume_name in volume_names
    )
    assert all(os.sep not in volume_name for volume_name in volume_names)


async def test_get_docker_volume(
    mounted_volumes: MountedVolumes,
    settings: DynamicSidecarSettings,
    inputs_dir: Path,
    outputs_dir: Path,
    state_paths_dirs: list[Path],
    ensure_external_volumes: tuple[DockerVolume],
):
    run_id = settings.DY_SIDECAR_RUN_ID
    docker_volumes_names = [v.name for v in ensure_external_volumes]

    # volume mounts expected as = "source:target"
    source, target = (await mounted_volumes.get_inputs_docker_volume(run_id)).split(":")
    assert any(name in source for name in docker_volumes_names)
    assert target == f"{inputs_dir}"

    source, target = (await mounted_volumes.get_outputs_docker_volume(run_id)).split(
        ":"
    )
    assert any(name in source for name in docker_volumes_names)
    assert target == f"{outputs_dir}"

    async for volume_bind in mounted_volumes.iter_state_paths_to_docker_volumes(run_id):
        source, target = volume_bind.split(":")
        assert any(name in source for name in docker_volumes_names)
        assert target in f"{state_paths_dirs}"
