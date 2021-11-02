from pathlib import Path

import pytest
from simcore_service_dask_sidecar.computational_sidecar.task_shared_volume import (
    TaskSharedVolumes,
)


async def test_shared_volume(tmp_path: Path):
    base_path = tmp_path / "pytest_folder"

    async with TaskSharedVolumes(base_path) as task_shared_volume:
        for folder in [
            task_shared_volume.inputs_folder,
            task_shared_volume.outputs_folder,
            task_shared_volume.logs_folder,
        ]:
            assert (base_path / folder).exists()

    for folder in [
        task_shared_volume.inputs_folder,
        task_shared_volume.outputs_folder,
        task_shared_volume.logs_folder,
    ]:
        assert not (base_path / folder).exists()
    assert not base_path.exists()


async def test_shared_volume_propagates_exception(tmp_path: Path):
    base_path = tmp_path / "pytest_folder"

    assert not base_path.exists()

    with pytest.raises(KeyError):
        async with TaskSharedVolumes(base_path):
            assert base_path.exists()
            raise KeyError("we create an error here")

    # ensure it is properly cleaned up
    assert not base_path.exists()


async def test_shared_volume_already_exists(tmp_path: Path):
    base_path = tmp_path / "pytest_folder"
    for folder in ["inputs", "outputs", "logs"]:
        (base_path / folder).mkdir(parents=True)
        assert (base_path / folder).exists()
        # we put some files in there
        (base_path / folder / "some_file").write_text("blahblahblah")
        assert (base_path / folder / "some_file").exists()

    async with TaskSharedVolumes(base_path):
        # it should have wiped out the old files
        assert base_path.exists()
        for folder in ["inputs", "outputs", "logs"]:
            assert not (base_path / folder / "some_file").exists()

    # ensure it is properly cleaned up
    assert not base_path.exists()
