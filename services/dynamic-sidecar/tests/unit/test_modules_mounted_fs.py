# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=protected-access

import os
from pathlib import Path

import pytest
from aiodocker.volumes import DockerVolume
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from models_library.services import RunID
from simcore_service_dynamic_sidecar.core.application import AppState
from simcore_service_dynamic_sidecar.models.shared_store import SharedStore
from simcore_service_dynamic_sidecar.modules.mounted_fs import (
    MountedVolumes,
    _name_from_full_path,
)

# UTILS


def _replace_slashes(path: Path) -> str:
    return str(path).replace(os.sep, "_")


# FIXTURES


@pytest.fixture
def path_to_transform() -> Path:
    return Path("/some/path/to/transform")


@pytest.fixture
def app(app: FastAPI) -> FastAPI:
    app.state.shared_store = SharedStore()  # emulate on_startup event
    return app


@pytest.fixture
def mounted_volumes(app: FastAPI) -> MountedVolumes:
    return AppState(app).mounted_volumes


# TESTS


def test_name_from_full_path(path_to_transform: Path):
    assert _name_from_full_path(  # pylint: disable=protected-access
        path_to_transform
    ) == _replace_slashes(path_to_transform)


def test_setup_ok(mounted_volumes: MountedVolumes):
    assert mounted_volumes


async def test_expected_paths_and_volumes(
    ensure_external_volumes: tuple[DockerVolume],
    mounted_volumes: MountedVolumes,
    inputs_dir: Path,
    outputs_dir: Path,
    state_paths_dirs: list[Path],
    run_id: RunID,
    node_id: NodeID,
):
    assert (
        len(set(mounted_volumes.volume_name_state_paths()))
        == len(
            {
                x
                async for x in mounted_volumes.iter_state_paths_to_docker_volumes(
                    run_id
                )
            }
        )
        == len(set(mounted_volumes.disk_state_paths()))
    )

    # check location on disk
    assert (
        mounted_volumes.disk_outputs_path
        == mounted_volumes._dy_volumes / outputs_dir.relative_to("/")
    )
    assert (
        mounted_volumes.disk_inputs_path
        == mounted_volumes._dy_volumes / inputs_dir.relative_to("/")
    )

    assert set(mounted_volumes.disk_state_paths()) == {
        mounted_volumes._dy_volumes / x.relative_to("/") for x in state_paths_dirs
    }

    # check volume mount point
    assert (
        mounted_volumes.volume_name_outputs
        == f"dyv_{run_id}{_replace_slashes(outputs_dir)}_{node_id}"
    )
    assert (
        mounted_volumes.volume_name_inputs
        == f"dyv_{run_id}{_replace_slashes(inputs_dir)}_{node_id}"
    )

    assert set(mounted_volumes.volume_name_state_paths()) == {
        f"dyv_{run_id}{_replace_slashes(x)}_{node_id}" for x in state_paths_dirs
    }

    def _get_container_mount(mount_path: str) -> str:
        return mount_path.split(":")[1]

    # check docker_volume
    assert (
        _get_container_mount(await mounted_volumes.get_inputs_docker_volume(run_id))
        == f"{mounted_volumes.inputs_path}"
    )
    assert (
        _get_container_mount(await mounted_volumes.get_outputs_docker_volume(run_id))
        == f"{mounted_volumes.outputs_path}"
    )

    assert {
        _get_container_mount(x)
        async for x in mounted_volumes.iter_state_paths_to_docker_volumes(run_id)
    } == {f"{state_path}" for state_path in state_paths_dirs}
