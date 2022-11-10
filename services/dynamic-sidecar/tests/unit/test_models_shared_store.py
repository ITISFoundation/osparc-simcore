# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest
from async_asgi_testclient import TestClient
from faker import Faker
from fastapi import FastAPI
from pytest_mock.plugin import MockerFixture
from simcore_service_dynamic_sidecar.core import application
from simcore_service_dynamic_sidecar.models.shared_store import (
    STORE_FILE_NAME,
    ContainerNameStr,
    SharedStore,
)


@pytest.fixture
def trigger_setup_shutdown_events(
    shared_store_dir: Path,
    app: FastAPI,
    mock_node_ports_v2_ports: None,
    test_client: TestClient,
) -> None:
    assert app.state.shared_store is not None


@pytest.fixture
def shared_store(trigger_setup_shutdown_events: None, app: FastAPI) -> SharedStore:
    return app.state.shared_store


@pytest.fixture
def fake_compose_spec(faker: Faker) -> str:
    return f"just_a_string_pretending_to_be_a_compose_spec_{faker.uuid4()}"


# mock docker_compose_down in application
@pytest.fixture
def mock_docker_compose(mocker: MockerFixture) -> None:
    mocker.patch.object(application, "docker_compose_down")


@dataclass
class UpdateFields:
    compose_spec: Optional[str]
    container_names: list[ContainerNameStr]


@pytest.mark.parametrize(
    "update_fields",
    [
        UpdateFields(compose_spec=None, container_names=[]),
        UpdateFields(compose_spec="some_random_fake_spec", container_names=[]),
        UpdateFields(
            compose_spec="some_random_fake_spec", container_names=["a_continaer"]
        ),
        UpdateFields(
            compose_spec="some_random_fake_spec", container_names=["a_ctnr", "b_cont"]
        ),
    ],
)
async def test_shared_store_updates(
    mock_docker_compose: None,
    shared_store: SharedStore,
    fake_compose_spec: str,
    ensure_shared_store_dir: Path,
    update_fields: UpdateFields,
):
    # check no file is present on the disk from where the data was created
    store_file_path = ensure_shared_store_dir / STORE_FILE_NAME
    assert store_file_path.exists() is False

    # change some data and trigger a persist
    shared_store.compose_spec = update_fields.compose_spec
    shared_store.container_names = update_fields.container_names
    await shared_store.persist_to_disk()

    # check the contes of the file should be the same as the shared_store's
    assert store_file_path.exists() is True
    assert shared_store == SharedStore.parse_raw(store_file_path.read_text())
