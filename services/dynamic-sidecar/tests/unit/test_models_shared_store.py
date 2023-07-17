# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from async_asgi_testclient import TestClient
from fastapi import FastAPI
from models_library.sidecar_volumes import VolumeCategory, VolumeState, VolumeStatus
from pydantic import parse_obj_as
from pytest_mock.plugin import MockerFixture
from servicelib.utils import logged_gather
from simcore_service_dynamic_sidecar.core import application
from simcore_service_dynamic_sidecar.models.shared_store import (
    STORE_FILE_NAME,
    SharedStore,
)


@pytest.fixture
def trigger_setup_shutdown_events(
    shared_store_dir: Path,
    app: FastAPI,
    test_client: TestClient,
) -> None:
    assert app.state.shared_store is not None


@pytest.fixture
def shared_store(trigger_setup_shutdown_events: None, app: FastAPI) -> SharedStore:
    return app.state.shared_store


# mock docker_compose_down in application
@pytest.fixture
def mock_docker_compose(mocker: MockerFixture) -> None:
    mocker.patch.object(application, "docker_compose_down")


@pytest.mark.parametrize(
    "update_fields",
    [
        {"compose_spec": None, "container_names": []},
        {"compose_spec": "some_random_fake_spec", "container_names": []},
        {"compose_spec": "some_random_fake_spec", "container_names": ["a_continaer"]},
        {
            "compose_spec": "some_random_fake_spec",
            "container_names": ["a_ctnr", "b_cont"],
        },
        {"volume_states": {}},
        {
            "volume_states": {
                VolumeCategory.OUTPUTS: parse_obj_as(
                    VolumeState, {"status": VolumeStatus.CONTENT_NO_SAVE_REQUIRED}
                ),
                VolumeCategory.INPUTS: parse_obj_as(
                    VolumeState, {"status": VolumeStatus.CONTENT_NEEDS_TO_BE_SAVED}
                ),
                VolumeCategory.STATES: parse_obj_as(
                    VolumeState, {"status": VolumeStatus.CONTENT_WAS_SAVED}
                ),
                VolumeCategory.SHARED_STORE: parse_obj_as(
                    VolumeState, {"status": VolumeStatus.CONTENT_NO_SAVE_REQUIRED}
                ),
            }
        },
    ],
)
async def test_shared_store_updates(
    mock_docker_compose: None,
    shared_store: SharedStore,
    ensure_shared_store_dir: Path,
    update_fields: dict[str, Any],
):
    # check no file is present on the disk from where the data was created
    store_file_path = ensure_shared_store_dir / STORE_FILE_NAME
    # file already exists since it was initialized, removing it for this test
    store_file_path.unlink()
    assert store_file_path.exists() is False

    # change some data and trigger a persist
    async with shared_store:
        for attr_name, attr_value in update_fields.items():
            setattr(shared_store, attr_name, attr_value)

    # check the contes of the file should be the same as the shared_store's
    assert store_file_path.exists() is True
    assert shared_store == SharedStore.parse_raw(store_file_path.read_text())


async def test_no_concurrency_with_parallel_writes(
    mock_docker_compose: None, shared_store: SharedStore, ensure_shared_store_dir: Path
):
    PARALLEL_CHANGES: int = 1000

    async def replace_list_in_shared_store(item: str):
        async with shared_store:
            new_list = deepcopy(shared_store.container_names)
            new_list.append(item)
            shared_store.container_names = new_list

    await logged_gather(
        *(replace_list_in_shared_store(f"{x}") for x in range(PARALLEL_CHANGES))
    )
    assert len(shared_store.container_names) == PARALLEL_CHANGES


async def test_init_from_disk_with_legacy_data_format(project_tests_dir: Path):
    MOCKS_DIR = project_tests_dir / "mocks"
    LEGACY_SHARED_STORE = "legacy_shared_store.json"

    results = await SharedStore.init_from_disk(
        MOCKS_DIR, store_file_name=LEGACY_SHARED_STORE
    )
    # if file is missing it correctly loaded the storage_file
    assert (MOCKS_DIR / STORE_FILE_NAME).exists() is False

    # ensure object content and disk content are the same
    assert json.loads(results.json()) == json.loads(
        (MOCKS_DIR / LEGACY_SHARED_STORE).read_text()
    )


async def test_init_from_disk_no_file_present(tmp_path: Path):
    await SharedStore.init_from_disk(tmp_path, store_file_name=STORE_FILE_NAME)
    assert (tmp_path / STORE_FILE_NAME).exists() is True
