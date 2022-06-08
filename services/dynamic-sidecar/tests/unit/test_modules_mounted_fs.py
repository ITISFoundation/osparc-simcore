# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=protected-access

import os
from pathlib import Path
from typing import List

import pytest
from simcore_service_dynamic_sidecar.modules import mounted_fs

# UTILS


def _replace_slashes(path: Path) -> str:
    return str(path).replace(os.sep, "_")


# FIXTURES


@pytest.fixture
def path_to_transform() -> Path:
    return Path("/some/path/to/transform")


# TESTS


def test_name_from_full_path(path_to_transform: Path) -> None:
    assert mounted_fs._name_from_full_path(  # pylint: disable=protected-access
        path_to_transform
    ) == _replace_slashes(path_to_transform)


def test_setup_ok(mounted_volumes: mounted_fs.MountedVolumes) -> None:
    assert mounted_volumes


async def test_expected_paths_and_volumes(
    mounted_volumes: mounted_fs.MountedVolumes,
    inputs_dir: Path,
    outputs_dir: Path,
    state_paths_dirs: List[Path],
    compose_namespace: str,
) -> None:
    assert (
        len(set(mounted_volumes.volume_name_state_paths()))
        == len({x async for x in mounted_volumes.iter_state_paths_to_docker_volumes()})
        == len(set(mounted_volumes.disk_state_paths()))
    )

    # check location on disk
    assert (
        mounted_volumes.disk_outputs_path
        == mounted_fs.DY_VOLUMES / outputs_dir.relative_to("/")
    )
    assert (
        mounted_volumes.disk_inputs_path
        == mounted_fs.DY_VOLUMES / inputs_dir.relative_to("/")
    )

    assert set(mounted_volumes.disk_state_paths()) == {
        mounted_fs.DY_VOLUMES / x.relative_to("/") for x in state_paths_dirs
    }

    # check volume mount point
    assert (
        mounted_volumes.volume_name_outputs
        == f"{compose_namespace}{_replace_slashes(outputs_dir)}"
    )
    assert (
        mounted_volumes.volume_name_inputs
        == f"{compose_namespace}{_replace_slashes(inputs_dir)}"
    )

    assert set(mounted_volumes.volume_name_state_paths()) == {
        f"{compose_namespace}{_replace_slashes(x)}" for x in state_paths_dirs
    }

    def _get_container_mount(mount_path: str) -> str:
        return mount_path.split(":")[1]

    # check docker_volume
    assert (
        _get_container_mount(await mounted_volumes.get_inputs_docker_volume())
        == f"{mounted_volumes.inputs_path}"
    )
    assert (
        _get_container_mount(await mounted_volumes.get_outputs_docker_volume())
        == f"{mounted_volumes.outputs_path}"
    )

    assert {
        _get_container_mount(x)
        async for x in mounted_volumes.iter_state_paths_to_docker_volumes()
    } == {f"{state_path}" for state_path in state_paths_dirs}
