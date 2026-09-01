# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=unused-argument

import asyncio
from collections.abc import Awaitable, Callable
from unittest import mock

import pytest
import sqlalchemy as sa
import sqlalchemy.ext.asyncio as sa_asyncio
from aiohttp.test_utils import TestClient
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStop,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    MockedStorageSubsystem,
    standard_role_response,
    standard_user_role_response,
)
from servicelib.aiohttp import status
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from simcore_postgres_database.models.projects_nodes import projects_nodes
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects import _projects_nodes_repository, _projects_repository
from simcore_service_webserver.projects.models import ProjectDict

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.mark.parametrize(
    "dy_service_running",
    [
        pytest.param(True, id="dy-service-running"),
        pytest.param(False, id="dy-service-NOT-running"),
    ],
)
@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_delete_node(
    mock_dynamic_scheduler: None,
    client: TestClient,
    logged_user: dict,
    user_project: ProjectDict,
    expected: ExpectedResponse,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    storage_subsystem_mock: MockedStorageSubsystem,
    dy_service_running: bool,
    postgres_db: sa.engine.Engine,
    create_dynamic_service_mock: Callable[..., Awaitable[DynamicServiceGet]],
):
    # first create a node
    assert client.app
    assert "workbench" in user_project
    assert isinstance(user_project["workbench"], dict)
    running_dy_services = [
        service_uuid
        for service_uuid, service_data in user_project["workbench"].items()
        if "/dynamic/" in service_data["key"] and dy_service_running
    ]
    _ = [
        await create_dynamic_service_mock(project_id=user_project["uuid"], service_uuid=service_uuid)
        for service_uuid in running_dy_services
    ]

    for node_id in user_project["workbench"]:
        url = client.app.router["delete_node"].url_for(project_id=user_project["uuid"], node_id=node_id)
        response = await client.delete(url.path)
        data, error = await assert_status(response, expected.no_content)
        assert not data
        if error:
            continue

        mocked_dynamic_services_interface["dynamic_scheduler.api.list_dynamic_services"].assert_called_once()
        mocked_dynamic_services_interface["dynamic_scheduler.api.list_dynamic_services"].reset_mock()

        if node_id in running_dy_services:
            mocked_dynamic_services_interface["dynamic_scheduler.api.stop_dynamic_service"].assert_called_once_with(
                mock.ANY,
                dynamic_service_stop=DynamicServiceStop(
                    user_id=logged_user["id"],
                    project_id=user_project["uuid"],
                    node_id=NodeID(node_id),
                    simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                    save_state=False,
                    product_name="osparc",
                ),
            )
            mocked_dynamic_services_interface["dynamic_scheduler.api.stop_dynamic_service"].reset_mock()
        else:
            mocked_dynamic_services_interface["dynamic_scheduler.api.stop_dynamic_service"].assert_not_called()

        # ensure the node is gone
        with postgres_db.connect() as conn:
            result = conn.execute(
                sa.select(sa.literal(1))
                .where((projects_nodes.c.project_uuid == user_project["uuid"]) & (projects_nodes.c.node_id == node_id))
                .limit(1)
            )
            assert result.scalar() is None


@pytest.mark.parametrize(
    "reference_field_override,override_value,expected_override_value,literal_with_deleted_node_id",
    [
        pytest.param("input_nodes", [], [], False, id="empty-input-nodes"),
        pytest.param("input_nodes", None, None, False, id="json-null-input-nodes"),
        pytest.param("input_nodes", sa.null(), None, False, id="null-input-nodes"),
        pytest.param("inputs", None, None, False, id="json-null-inputs"),
        pytest.param("inputs", sa.null(), None, False, id="null-inputs"),
        pytest.param("inputs", {"literal": False}, {"literal": False}, False, id="unlinked-input-value"),
        pytest.param("inputs", {}, {}, True, id="literal-dictionary-containing-node-uuid"),
    ],
)
@pytest.mark.parametrize(*standard_user_role_response())
async def test_delete_node_removes_references_in_connected_nodes(
    mock_dynamic_scheduler: None,
    client: TestClient,
    logged_user: dict,
    user_project: ProjectDict,
    expected: ExpectedResponse,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    storage_subsystem_mock: MockedStorageSubsystem,
    postgres_db: sa.engine.Engine,
    reference_field_override: str,
    override_value: object,
    expected_override_value: list[str] | dict[str, object] | None,
    literal_with_deleted_node_id: bool,
):
    assert client.app
    workbench = user_project["workbench"]
    assert isinstance(workbench, dict)

    # find a node that is referenced by at least another one
    deleted_node_id = next(
        node_id
        for node_id in workbench
        if any(node_id in (other.get("inputNodes") or []) for other in workbench.values())
    )
    dependent_node_ids = [
        node_id for node_id, node_data in workbench.items() if deleted_node_id in (node_data.get("inputNodes") or [])
    ]
    assert dependent_node_ids

    if literal_with_deleted_node_id:
        literal_input: dict[str, object] = {
            "literal": {
                "kind": "metadata",
                "nodeUuid": deleted_node_id,
            }
        }
        override_value = literal_input
        expected_override_value = literal_input

    with postgres_db.begin() as conn:
        conn.execute(
            projects_nodes.update()
            .where(
                (projects_nodes.c.project_uuid == user_project["uuid"])
                & (projects_nodes.c.node_id == dependent_node_ids[0])
            )
            .values(**{reference_field_override: override_value})
        )

    url = client.app.router["delete_node"].url_for(project_id=user_project["uuid"], node_id=deleted_node_id)
    response = await client.delete(url.path)
    await assert_status(response, expected.no_content)

    with postgres_db.connect() as conn:
        rows = conn.execute(
            sa.select(
                projects_nodes.c.node_id,
                projects_nodes.c.inputs,
                projects_nodes.c.input_nodes,
            ).where(projects_nodes.c.project_uuid == user_project["uuid"])
        ).fetchall()

    assert {row.node_id for row in rows} == set(workbench) - {deleted_node_id}
    for row in rows:
        expected_input_nodes = workbench[row.node_id].get("inputNodes")
        expected_inputs = workbench[row.node_id].get("inputs")

        if row.node_id == dependent_node_ids[0]:
            if reference_field_override == "input_nodes":
                expected_input_nodes = expected_override_value
            else:
                expected_inputs = expected_override_value

        if expected_input_nodes is not None:
            expected_input_nodes = [node_id for node_id in expected_input_nodes if node_id != deleted_node_id]
        if expected_inputs is not None:
            assert isinstance(expected_inputs, dict)
            expected_inputs = {
                key: value
                for key, value in expected_inputs.items()
                if not (
                    isinstance(value, dict)
                    and set(value) == {"nodeUuid", "output"}
                    and value.get("nodeUuid") == deleted_node_id
                )
            }

        assert row.input_nodes == expected_input_nodes
        assert row.inputs == expected_inputs


@pytest.mark.parametrize(*standard_user_role_response())
async def test_delete_node_rolls_back_reference_pruning_if_delete_fails(
    mock_dynamic_scheduler: None,
    client: TestClient,
    user_project: ProjectDict,
    expected: ExpectedResponse,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    storage_subsystem_mock: MockedStorageSubsystem,
    postgres_db: sa.engine.Engine,
    mocker: MockerFixture,
):
    assert client.app
    workbench = user_project["workbench"]
    assert isinstance(workbench, dict)

    deleted_node_id = next(
        node_id
        for node_id in workbench
        if any(node_id in (other.get("inputNodes") or []) for other in workbench.values())
    )

    query = sa.select(
        projects_nodes.c.node_id,
        projects_nodes.c.inputs,
        projects_nodes.c.input_nodes,
    ).where(projects_nodes.c.project_uuid == user_project["uuid"])
    with postgres_db.connect() as conn:
        original_nodes = {row.node_id: (row.inputs, row.input_nodes) for row in conn.execute(query)}

    update_spy = mocker.spy(_projects_nodes_repository, "update")
    mocker.patch.object(
        _projects_nodes_repository,
        "delete",
        side_effect=RuntimeError("injected node deletion failure"),
    )

    url = client.app.router["delete_node"].url_for(project_id=user_project["uuid"], node_id=deleted_node_id)
    response = await client.delete(url.path)
    await assert_status(response, status.HTTP_500_INTERNAL_SERVER_ERROR)

    assert update_spy.await_count > 0
    with postgres_db.connect() as conn:
        current_nodes = {row.node_id: (row.inputs, row.input_nodes) for row in conn.execute(query)}

    assert current_nodes == original_nodes


@pytest.mark.parametrize(
    "first_operation,expected_patch_status",
    [
        pytest.param("delete", status.HTTP_404_NOT_FOUND, id="delete-first"),
        pytest.param("patch", status.HTTP_204_NO_CONTENT, id="patch-first"),
    ],
)
@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_delete_node_and_graph_patch_are_serialized(
    mock_dynamic_scheduler: None,
    client: TestClient,
    user_project: ProjectDict,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    storage_subsystem_mock: MockedStorageSubsystem,
    postgres_db: sa.engine.Engine,
    mocker: MockerFixture,
    first_operation: str,
    expected_patch_status: int,
):
    assert client.app
    deleted_node_id, patched_node_id = list(user_project["workbench"])[:2]
    delete_url = client.app.router["delete_node"].url_for(project_id=user_project["uuid"], node_id=deleted_node_id)
    patch_url = client.app.router["patch_project_node"].url_for(
        project_id=user_project["uuid"], node_id=patched_node_id
    )
    patch = {
        "inputNodes": [deleted_node_id],
        "inputs": {
            "input_1": {
                "nodeUuid": deleted_node_id,
                "output": "out_1",
            }
        },
    }

    original_lock_project_graph = _projects_repository.lock_project_graph
    first_lock_acquired = asyncio.Event()
    release_first_lock = asyncio.Event()
    second_lock_attempted = asyncio.Event()
    lock_call_count = 0

    async def _lock_project_graph(
        connection: sa_asyncio.AsyncConnection,
        *,
        project_uuid: ProjectID,
    ) -> None:
        nonlocal lock_call_count
        lock_call_count += 1
        call_number = lock_call_count
        if call_number == 2:
            second_lock_attempted.set()
        await original_lock_project_graph(connection, project_uuid=project_uuid)
        if call_number == 1:
            first_lock_acquired.set()
            await release_first_lock.wait()

    mocker.patch.object(_projects_repository, "lock_project_graph", side_effect=_lock_project_graph)

    requests = {
        "delete": lambda: client.delete(delete_url.path),
        "patch": lambda: client.patch(patch_url.path, json=patch),
    }
    second_operation = "patch" if first_operation == "delete" else "delete"
    first_request = asyncio.create_task(requests[first_operation]())
    await asyncio.wait_for(first_lock_acquired.wait(), timeout=10)
    second_request = asyncio.create_task(requests[second_operation]())
    try:
        await asyncio.wait_for(second_lock_attempted.wait(), timeout=10)
    finally:
        release_first_lock.set()

    first_response, second_response = await asyncio.gather(first_request, second_request)
    responses = {first_operation: first_response, second_operation: second_response}
    await assert_status(responses["delete"], status.HTTP_204_NO_CONTENT)
    await assert_status(responses["patch"], expected_patch_status)

    with postgres_db.connect() as conn:
        patched_node = conn.execute(
            sa.select(projects_nodes.c.inputs, projects_nodes.c.input_nodes).where(
                (projects_nodes.c.project_uuid == user_project["uuid"]) & (projects_nodes.c.node_id == patched_node_id)
            )
        ).one()

    assert deleted_node_id not in (patched_node.input_nodes or [])
    assert not any(
        isinstance(value, dict) and value.get("nodeUuid") == deleted_node_id
        for value in (patched_node.inputs or {}).values()
    )
