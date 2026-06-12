# pylint: disable=redefined-outer-name
# pylint: disable=protected-access
# pylint: disable=unused-argument

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture
from simcore_service_webserver.projects import _projects_service


@pytest.fixture
def mock_not_locked(mocker: MockerFixture) -> None:
    mocker.patch.object(_projects_service, "get_redis_lock_manager_client_sdk", return_value=Mock())
    mocker.patch.object(_projects_service, "is_project_locked", AsyncMock(return_value=False))


@pytest.fixture
def mock_retrieve_inputs(mocker: MockerFixture) -> AsyncMock:
    retrieve_inputs = AsyncMock(return_value=None)
    mocker.patch.object(
        _projects_service.dynamic_scheduler_service,
        "retrieve_inputs",
        retrieve_inputs,
    )
    return retrieve_inputs


async def test_trigger_connected_service_retrieve_uses_camelcase_alias(
    mock_not_locked: None, mock_retrieve_inputs: AsyncMock
):
    """The post-refactor workbench (rebuilt from projects_nodes) stores port
    links with the `nodeUuid` alias. Verify the linked-input lookup works
    without relying on the legacy `node_uuid` snake_case fallback.
    """
    project_id = str(uuid4())
    updated_node_id = str(uuid4())
    downstream_node_id = str(uuid4())

    workbench = {
        updated_node_id: {
            "key": "simcore/services/comp/upstream",
            "version": "1.0.0",
            "label": "upstream",
        },
        downstream_node_id: {
            "key": "simcore/services/dynamic/downstream",
            "version": "1.0.0",
            "label": "downstream",
            "inputs": {
                "in_1": {"nodeUuid": updated_node_id, "output": "out_1"},
                "in_2": {"nodeUuid": updated_node_id, "output": "out_unchanged"},
                "in_3": 42,
            },
        },
    }

    await _projects_service._trigger_connected_service_retrieve(  # noqa: SLF001
        app=Mock(),
        project={"uuid": project_id, "workbench": workbench},
        updated_node_uuid=updated_node_id,
        changed_keys=["out_1"],
    )

    assert mock_retrieve_inputs.await_count == 1
    args, _ = mock_retrieve_inputs.await_args
    # signature: (app, NodeID(node_id), keys)
    assert str(args[1]) == downstream_node_id
    assert args[2] == ["in_1"]


async def test_trigger_connected_service_retrieve_skips_when_locked(
    mocker: MockerFixture, mock_retrieve_inputs: AsyncMock
):
    mocker.patch.object(_projects_service, "get_redis_lock_manager_client_sdk", return_value=Mock())
    mocker.patch.object(_projects_service, "is_project_locked", AsyncMock(return_value=True))

    await _projects_service._trigger_connected_service_retrieve(  # noqa: SLF001
        app=Mock(),
        project={"uuid": str(uuid4()), "workbench": {}},
        updated_node_uuid=str(uuid4()),
        changed_keys=["out_1"],
    )

    mock_retrieve_inputs.assert_not_awaited()
