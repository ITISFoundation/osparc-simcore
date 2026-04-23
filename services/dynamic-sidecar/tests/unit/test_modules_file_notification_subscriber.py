# pylint:disable=redefined-outer-name

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_messages import (
    FileNotificationEventType,
    FileNotificationMessage,
)
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from pytest_mock import MockerFixture
from simcore_service_dynamic_sidecar.modules.file_notification_subscriber import (
    _handle_file_notification,
    _resolve_local_path_from_storage_id,
)
from simcore_service_dynamic_sidecar.modules.mounted_fs import MountedVolumes


@pytest.fixture()
def project_id(faker: Faker) -> ProjectID:
    return faker.uuid4(cast_to=None)


@pytest.fixture()
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture()
def file_id(project_id: ProjectID, node_id: NodeID) -> str:
    return f"{project_id}/{node_id}/some-file.txt"


@pytest.fixture()
def user_id(faker: Faker) -> UserID:
    return faker.pyint(min_value=1)


@pytest.fixture()
def mock_notify_path_change(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch(
        "simcore_service_dynamic_sidecar.modules.file_notification_subscriber._notify_path_change",
        autospec=True,
    )


@pytest.mark.parametrize(
    "event_type",
    list(FileNotificationEventType),
)
async def test_handle_file_notification_calls_notify_path_change(
    mock_notify_path_change: AsyncMock,
    event_type: FileNotificationEventType,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    file_id: str,
):
    message = FileNotificationMessage(
        event_type=event_type,
        user_id=user_id,
        file_id=file_id,
        project_id=project_id,
        node_id=node_id,
    )
    data = message.body()

    result = await _handle_file_notification(None, data)

    assert result is True
    mock_notify_path_change.assert_awaited_once_with(app=None, event_type=event_type, path=file_id, recursive=False)


async def test_handle_file_notification_with_optional_ids(
    mock_notify_path_change: AsyncMock,
    file_id: str,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
):
    message = FileNotificationMessage(
        event_type=FileNotificationEventType.FILE_UPLOADED,
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        file_id=file_id,
    )
    data = message.body()

    result = await _handle_file_notification(None, data)

    assert result is True
    mock_notify_path_change.assert_awaited_once_with(
        app=None, event_type=FileNotificationEventType.FILE_UPLOADED, path=file_id, recursive=False
    )


_INPUTS_PATH = Path("/inputs")
_OUTPUTS_PATH = Path("/outputs")
_STATE_PATH_A = Path("/workspace/state-a")
_STATE_PATH_B = Path("/workspace/state-b")


@pytest.fixture()
def mounted_volumes(tmp_path: Path, faker: Faker, node_id: NodeID) -> MountedVolumes:
    return MountedVolumes(
        service_run_id=ServiceRunID(faker.uuid4()),
        node_id=node_id,
        inputs_path=_INPUTS_PATH,
        outputs_path=_OUTPUTS_PATH,
        user_preferences_path=None,
        state_paths=[_STATE_PATH_A, _STATE_PATH_B],
        state_exclude=set(),
        compose_namespace="test-namespace",
        dy_volumes=tmp_path,
    )


def _make_storage_id(project_id: ProjectID, node_id: NodeID, volume_name: str, *parts: str) -> str:
    return "/".join((f"{project_id}", f"{node_id}", volume_name, *parts))


@pytest.mark.parametrize(
    "state_path_index, sub_parts",
    [
        pytest.param(0, ("sub", "file.bin"), id="first-state-volume-with-subdir"),
        pytest.param(1, ("file.bin",), id="second-state-volume-flat"),
    ],
)
def test_resolve_local_path_for_state_volume_resolves_correctly(
    mounted_volumes: MountedVolumes,
    project_id: ProjectID,
    node_id: NodeID,
    state_path_index: int,
    sub_parts: tuple[str, ...],
):
    state_paths = [_STATE_PATH_A, _STATE_PATH_B]
    state_disk_paths = list(mounted_volumes.disk_state_paths_iter())
    storage_id = _make_storage_id(project_id, node_id, state_paths[state_path_index].name, *sub_parts)

    resolved = _resolve_local_path_from_storage_id(mounted_volumes, storage_id)

    assert resolved is not None
    expected = state_disk_paths[state_path_index].joinpath(*sub_parts).resolve()
    assert resolved == expected


@pytest.mark.parametrize(
    "volume_path",
    [
        pytest.param(_INPUTS_PATH, id="inputs"),
        pytest.param(_OUTPUTS_PATH, id="outputs"),
    ],
)
def test_resolve_local_path_for_inputs_and_outputs_returns_none(
    mounted_volumes: MountedVolumes,
    project_id: ProjectID,
    node_id: NodeID,
    volume_path: Path,
):
    """Regression: inputs/outputs volumes MUST NOT be resolved by the bind-mount fallback.

    Resolving outputs would cause the dynamic-sidecar to download (via the file-notification
    fallback) the file it just uploaded, into the very directory the outputs watcher is
    observing — re-triggering the upload and producing an infinite loop.
    """
    storage_id = _make_storage_id(project_id, node_id, volume_path.name, "some-file.txt")

    assert _resolve_local_path_from_storage_id(mounted_volumes, storage_id) is None


@pytest.mark.parametrize(
    "storage_id_template",
    [
        pytest.param(
            "{project_id}/{node_id}/not-a-volume/file.bin",
            id="unknown-volume",
        ),
        pytest.param(
            "only/two",
            id="too-few-parts",
        ),
        pytest.param(
            f"{{project_id}}/{{node_id}}/{_STATE_PATH_A.name}/../../etc/passwd",
            id="path-traversal",
        ),
    ],
)
def test_resolve_local_path_returns_none_on_invalid_storage_ids(
    mounted_volumes: MountedVolumes,
    project_id: ProjectID,
    node_id: NodeID,
    storage_id_template: str,
):
    storage_id = storage_id_template.format(project_id=project_id, node_id=node_id)

    assert _resolve_local_path_from_storage_id(mounted_volumes, storage_id) is None
