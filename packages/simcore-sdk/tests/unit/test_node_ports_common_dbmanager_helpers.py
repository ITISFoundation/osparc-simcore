# pylint: disable=protected-access

import types
from unittest.mock import AsyncMock

from simcore_sdk.node_ports_common import dbmanager


async def test_update_comp_run_snapshot_tasks_if_computational(monkeypatch):
    engine = AsyncMock()
    connection = AsyncMock()
    project_id = "project-1"
    node_uuid = "node-1"
    node_configuration = {
        "schema": {"foo": "bar"},
        "inputs": {"a": 1},
        "outputs": {"b": 2},
        "run_hash": "hash123",
    }
    node = types.SimpleNamespace(node_class="COMPUTATIONAL")

    get_node_mock = AsyncMock(return_value=node)
    get_latest_run_id_mock = AsyncMock(return_value="run-1")
    update_mock = AsyncMock()

    monkeypatch.setattr(dbmanager, "_get_node_from_db", get_node_mock)
    monkeypatch.setattr(
        dbmanager, "get_latest_run_id_for_project", get_latest_run_id_mock
    )
    monkeypatch.setattr(dbmanager, "update_for_run_id_and_node_id", update_mock)

    await dbmanager._update_comp_run_snapshot_tasks_if_computational(
        engine, connection, project_id, node_uuid, node_configuration
    )

    get_node_mock.assert_awaited_once_with(project_id, node_uuid, connection)
    get_latest_run_id_mock.assert_awaited_once_with(
        engine, connection, project_id=project_id
    )
    update_mock.assert_awaited_once()
    _, kwargs = update_mock.call_args
    assert kwargs["run_id"] == "run-1"
    assert kwargs["node_id"] == node_uuid
    assert kwargs["data"]["schema"] == node_configuration["schema"]


async def test_update_comp_run_snapshot_tasks_if_not_computational(monkeypatch):
    engine = AsyncMock()
    connection = AsyncMock()
    project_id = "project-2"
    node_uuid = "node-2"
    node_configuration = {
        "schema": {},
        "inputs": {},
        "outputs": {},
    }
    node = types.SimpleNamespace(node_class="ITERATIVE")

    get_node_mock = AsyncMock(return_value=node)
    get_latest_run_id_mock = AsyncMock()
    update_mock = AsyncMock()

    monkeypatch.setattr(dbmanager, "_get_node_from_db", get_node_mock)
    monkeypatch.setattr(
        dbmanager, "get_latest_run_id_for_project", get_latest_run_id_mock
    )
    monkeypatch.setattr(dbmanager, "update_for_run_id_and_node_id", update_mock)

    await dbmanager._update_comp_run_snapshot_tasks_if_computational(
        engine, connection, project_id, node_uuid, node_configuration
    )

    get_node_mock.assert_awaited_once_with(project_id, node_uuid, connection)
    get_latest_run_id_mock.assert_not_awaited()
    update_mock.assert_not_awaited()
