# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=protected-access

import os
from pathlib import Path
from typing import Any, Iterator, List

import pytest
from simcore_service_dynamic_sidecar.modules import mounted_fs

# UTILS


def _replace_slashes(path: Path) -> str:
    return str(path).replace(os.sep, "_")


def _assert_same_object(first: Any, second: Any) -> None:
    assert first == second
    assert id(first) == id(second)


# FIXTURES


@pytest.fixture
def clear_mounted_volumes() -> Iterator[None]:
    mounted_fs._mounted_volumes = None
    yield
    mounted_fs._mounted_volumes = None


@pytest.fixture
def mounted_volumes(clear_mounted_volumes: None) -> mounted_fs.MountedVolumes:
    assert mounted_fs._mounted_volumes is None
    mounted_volumes: mounted_fs.MountedVolumes = mounted_fs.setup_mounted_fs()
    _assert_same_object(mounted_volumes, mounted_fs.get_mounted_volumes())
    return mounted_volumes


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


def test_expected_paths_and_volumes(
    mounted_volumes: mounted_fs.MountedVolumes,
    inputs_dir: Path,
    outputs_dir: Path,
    state_paths_dirs: List[Path],
    compose_namespace: str,
) -> None:
    assert (
        len(set(mounted_volumes.volume_name_state_paths()))
        == len(set(mounted_volumes.get_state_paths_docker_volumes()))
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

    # check docker_volume
    assert (
        mounted_volumes.get_inputs_docker_volume()
        == f"{mounted_volumes.volume_name_inputs}:{mounted_volumes.inputs_path}"
    )
    assert (
        mounted_volumes.get_outputs_docker_volume()
        == f"{mounted_volumes.volume_name_outputs}:{mounted_volumes.outputs_path}"
    )

    assert set(mounted_volumes.get_state_paths_docker_volumes()) == {
        f"{volume_state_path}:{state_path}"
        for volume_state_path, state_path in zip(
            mounted_volumes.volume_name_state_paths(), state_paths_dirs
        )
    }
