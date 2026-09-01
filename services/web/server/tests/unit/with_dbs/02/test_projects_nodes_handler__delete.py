# pylint: disable=too-many-arguments
# pylint: disable=unused-argument

from collections.abc import Awaitable, Callable
from unittest import mock

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStop,
)
from models_library.projects_nodes_io import NodeID
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    MockedStorageSubsystem,
    standard_role_response,
    standard_user_role_response,
)
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from simcore_postgres_database.models.projects_nodes import projects_nodes
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
    "reference_field_override,override_value,expected_override_value,legacy_input_link",
    [
        pytest.param("input_nodes", [], [], False, id="empty-input-nodes"),
        pytest.param("input_nodes", None, None, False, id="json-null-input-nodes"),
        pytest.param("input_nodes", sa.null(), None, False, id="null-input-nodes"),
        pytest.param("inputs", None, None, False, id="json-null-inputs"),
        pytest.param("inputs", {"literal": False}, {"literal": False}, True, id="legacy-linked-input-value"),
        pytest.param("inputs", sa.null(), None, False, id="null-inputs"),
        pytest.param("inputs", {"literal": False}, {"literal": False}, False, id="unlinked-input-value"),
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
    legacy_input_link: bool,
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

    with postgres_db.begin() as conn:
        override_values = {reference_field_override: override_value}
        if legacy_input_link:
            assert isinstance(override_value, dict)
            override_values.update(
                input_nodes=[],
                inputs={
                    **override_value,
                    "legacy-link": {"node_uuid": deleted_node_id, "output": "output"},
                },
            )
        conn.execute(
            projects_nodes.update()
            .where(
                (projects_nodes.c.project_uuid == user_project["uuid"])
                & (projects_nodes.c.node_id == dependent_node_ids[0])
            )
            .values(**override_values)
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
            if legacy_input_link:
                expected_input_nodes = []
                expected_inputs = expected_override_value
            elif reference_field_override == "input_nodes":
                expected_input_nodes = expected_override_value
            else:
                expected_inputs = expected_override_value

        if expected_input_nodes is not None:
            expected_input_nodes = [node_id for node_id in expected_input_nodes if node_id != deleted_node_id]
        if expected_inputs is not None:
            expected_inputs = {
                key: value
                for key, value in expected_inputs.items()
                if not (
                    isinstance(value, dict)
                    and (value.get("nodeUuid") == deleted_node_id or value.get("node_uuid") == deleted_node_id)
                )
            }

        assert row.input_nodes == expected_input_nodes
        assert row.inputs == expected_inputs
