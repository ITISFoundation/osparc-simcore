# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""Tests for the COPY project section of `_projects_service.py`:

- `clone_project_data` (shared clone primitive, also used by studies_dispatcher)
- `_clone_project_nodes` / `_remap_port_links_in_inputs` (helpers)
- `copy_allow_guests_to_push_states_and_output_ports`

NOTE: `clone_project_data` is meant to (in a future PR) replace part of the copy/clone
logic currently duplicated in `_crud_api_create.create_project`. The scenarios covered
here are inspired by the handler-level tests in `test_projects_crud_handlers.py`
(`test_new_project_from_template`, `test_new_project_from_other_study`,
`test_new_template_from_project`).
"""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from celery_library.async_jobs import AsyncJobResultUpdate
from common_library.users_enums import UserRole
from faker import Faker
from models_library.api_schemas_async_jobs.async_jobs import AsyncJobStatus
from models_library.api_schemas_long_running_tasks.base import TaskProgress
from models_library.products import ProductName
from models_library.progress_bar import ProgressReport
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, NodeIDStr, PortLink
from models_library.users import UserID
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.webserver_projects import NewProject
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_service_webserver.projects import _groups_service, _projects_service
from simcore_service_webserver.projects import (
    _projects_repository as projects_repository,
)
from simcore_service_webserver.projects._projects_repository_legacy import (
    ProjectDBAPI,
)
from simcore_service_webserver.projects._projects_service import (
    _clone_project_nodes,
    _remap_port_links_in_inputs,
    clone_project_data,
    copy_allow_guests_to_push_states_and_output_ports,
)
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.projects.utils import NodesMap


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


@pytest.fixture
def fake_project(fake_project: ProjectDict, workbench_db_column: dict[str, Any]) -> ProjectDict:
    # OVERRIDES session-level `fake_project`: use a workbench with interconnected
    # nodes (port links + input_nodes) so remap logic can be exercised end-to-end.
    project = deepcopy(fake_project)
    project["workbench"] = workbench_db_column
    return project


@pytest.fixture
def task_progress() -> TaskProgress:
    return TaskProgress.create()


@pytest.fixture
async def storage_subsystem_mock_override(mocker: MockerFixture, faker: Faker) -> None:
    """Mocks `storage_service.copy_data_folders_from_project` used by `clone_project_data`.

    NOTE: this is a DIFFERENT patch target than the `storage_subsystem_mock` fixture
    (which patches `_crud_api_create.copy_data_folders_from_project`, used by `create_project`).
    """
    mock_fn = mocker.patch(
        "simcore_service_webserver.projects._projects_service.storage_service.copy_data_folders_from_project",
        autospec=True,
    )

    async def _mock_copy(
        app: web.Application,
        *,
        source_project: ProjectDict,
        destination_project: ProjectDict,
        nodes_map: NodesMap,
        user_id: UserID,
        product_name: str,
    ):
        yield AsyncJobResultUpdate(
            AsyncJobStatus(
                job_id=faker.uuid4(cast_to=None),
                progress=ProgressReport(actual_value=0),
                done=False,
            )
        )

        async def _mock_result() -> None:
            return None

        yield AsyncJobResultUpdate(
            AsyncJobStatus(
                job_id=faker.uuid4(cast_to=None),
                progress=ProgressReport(actual_value=1),
                done=True,
            ),
            _mock_result(),
        )

    mock_fn.side_effect = _mock_copy


@pytest.fixture
async def template_project_with_params(
    client: TestClient,
    fake_project: ProjectDict,
    tests_data_dir: Path,
    osparc_product_name: ProductName,
    all_group: dict[str, str],
    user: UserInfoDict,
):
    # A template project whose workbench contains "{{ param }}"-style placeholders
    # and a port-link (`initfile`), reusing `tests/data/parametrized_project.json`.
    parametrized_workbench = json.loads((tests_data_dir / "parametrized_project.json").read_text())["workbench"]

    project_data = deepcopy(fake_project)
    project_data["name"] = "Fake parametrized template"
    project_data["uuid"] = "a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1"
    project_data["workbench"] = parametrized_workbench
    # grant read access to all users (`logged_user` is a different user than `user`)
    project_data["accessRights"] = {str(all_group["gid"]): {"read": True, "write": False, "delete": False}}

    async with NewProject(
        project_data,
        client.app,
        user_id=user["id"],
        product_name=osparc_product_name,
        tests_data_dir=tests_data_dir,
        as_template=True,
    ) as template_project:
        yield template_project


async def _get_inserted_nodes(app, project_uuid: str) -> dict[NodeID, Any]:
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)
    return {node.node_id: node for node in await db.list_project_nodes(ProjectID(project_uuid))}


async def _fetch_source_project(app, project_uuid: str, user_id: int) -> ProjectDict:
    """Fetches a project the same way `_prepare_project_copy` does in `_crud_api_create.py`.

    NOTE: the `user_project`/`template_project` fixtures return a test-helper-only
    dict shape (e.g. with a `trashedAt` key that doesn't round-trip through
    `convert_to_db_names`). Real callers of `clone_project_data` always obtain
    `source_project` via `get_project_for_user`, so tests do the same.
    """
    return await _projects_service.get_project_for_user(app, project_uuid=project_uuid, user_id=user_id)


#
# _remap_port_links_in_inputs
#


def test_remap_port_links_in_inputs_with_none_or_empty():
    # ACT & ASSERT
    assert _remap_port_links_in_inputs(None, {}) is None
    assert _remap_port_links_in_inputs({}, {}) == {}


def test_remap_port_links_in_inputs_with_dict_form():
    # SETUP
    nodes_map: NodesMap = {NodeIDStr("old-node-id"): NodeIDStr("new-node-id")}
    inputs = {
        "input_1": {"nodeUuid": "old-node-id", "output": "out_1"},
        "input_2": {"nodeUuid": "unmapped-node-id", "output": "out_1"},
        "input_3": 42,
    }

    # ACT
    remapped = _remap_port_links_in_inputs(inputs, nodes_map)

    # ASSERT
    assert remapped is not None
    assert remapped["input_1"] == {"nodeUuid": "new-node-id", "output": "out_1"}
    # unmapped uuids are left as-is
    assert remapped["input_2"] == {"nodeUuid": "unmapped-node-id", "output": "out_1"}
    # non-link values pass through untouched
    assert remapped["input_3"] == 42


def test_remap_port_links_in_inputs_with_portlink_form():
    # SETUP
    old_node_id = NodeID("38a0d401-af4b-4ea7-ab4c-5005c712a546")
    new_node_id = NodeID("13220a1d-a569-49de-b375-904301af9295")
    nodes_map: NodesMap = {NodeIDStr(f"{old_node_id}"): NodeIDStr(f"{new_node_id}")}
    inputs = {"input_1": PortLink(nodeUuid=old_node_id, output="out_1")}

    # ACT
    remapped = _remap_port_links_in_inputs(inputs, nodes_map)

    # ASSERT
    assert remapped is not None
    remapped_link = remapped["input_1"]
    assert isinstance(remapped_link, PortLink)
    assert remapped_link.node_uuid == new_node_id
    assert remapped_link.output == "out_1"


#
# clone_project_data
#


async def test_clone_project_data_from_standard_project(
    client: TestClient,
    logged_user: UserInfoDict,
    shared_project: ProjectDict,
    osparc_product_name: ProductName,
    task_progress: TaskProgress,
    mocked_dynamic_services_interface: dict[str, MockType],
    mock_dynamic_scheduler: None,
    storage_subsystem_mock_override: None,
):
    assert client.app

    # SETUP
    # `shared_project` is owned by `logged_user` but also shared (read-only) with `all_group`
    source_project = await _fetch_source_project(client.app, shared_project["uuid"], logged_user["id"])
    assert len(source_project["accessRights"]) > 1

    # ACT
    cloned_project = await clone_project_data(
        client.app,
        source_project=source_project,
        forced_copy_project_id=None,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        product_api_base_url="http://product.testserver.io",
        task_progress=task_progress,
    )

    # ASSERT
    # new project has a new uuid
    assert cloned_project["uuid"] != shared_project["uuid"]

    assert "accessRights" not in cloned_project
    owner_gid = logged_user["primary_gid"]
    project_groups = await _groups_service.list_project_groups_by_project_without_checking_permissions(
        client.app, project_id=ProjectID(cloned_project["uuid"])
    )
    assert {group.gid for group in project_groups} == {owner_gid}
    owner_group = project_groups[0]
    assert (owner_group.read, owner_group.write, owner_group.delete) == (True, True, True)

    # node uuids were regenerated (1-to-1 with the source workbench)
    assert set(cloned_project["workbench"].keys()) != set(shared_project["workbench"].keys())
    assert len(cloned_project["workbench"]) == len(shared_project["workbench"])

    # port-links (nodeUuid) and input_nodes were remapped to the new node uuids
    for node_data in cloned_project["workbench"].values():
        for input_node_id in node_data.get("inputNodes", []):
            assert input_node_id in cloned_project["workbench"]
        for port_value in node_data.get("inputs", {}).values():
            if isinstance(port_value, dict) and "nodeUuid" in port_value:
                assert port_value["nodeUuid"] in cloned_project["workbench"]

    # the project + its nodes were persisted
    inserted_nodes = await _get_inserted_nodes(client.app, cloned_project["uuid"])
    assert {f"{node_id}" for node_id in inserted_nodes} == set(cloned_project["workbench"].keys())

    # external services were called
    mocked_dynamic_services_interface["director_v2.api.create_or_update_pipeline"].assert_called_once()


async def test_clone_project_data_with_forced_project_id(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: ProductName,
    task_progress: TaskProgress,
    mocked_dynamic_services_interface: dict[str, MockType],
    mock_dynamic_scheduler: None,
    storage_subsystem_mock_override: None,
    faker: Faker,
):
    # SETUP
    assert client.app
    forced_project_id = ProjectID(faker.uuid4())
    source_project = await _fetch_source_project(client.app, user_project["uuid"], logged_user["id"])

    # ACT
    cloned_project = await clone_project_data(
        client.app,
        source_project=source_project,
        forced_copy_project_id=forced_project_id,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        product_api_base_url="http://product.testserver.io",
        task_progress=task_progress,
    )

    # ASSERT
    assert cloned_project["uuid"] == f"{forced_project_id}"


async def test_clone_project_data_locks_source_project_only_if_not_template(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    template_project: ProjectDict,
    osparc_product_name: ProductName,
    task_progress: TaskProgress,
    mocked_dynamic_services_interface: dict[str, MockType],
    mock_dynamic_scheduler: None,
    storage_subsystem_mock_override: None,
    mocker: MockerFixture,
):
    # SETUP
    assert client.app
    spied_with_project_locked = mocker.spy(_projects_service, "with_project_locked")

    # ACT: cloning a STANDARD project locks the source while copying data
    standard_source_project = await _fetch_source_project(client.app, user_project["uuid"], logged_user["id"])
    await clone_project_data(
        client.app,
        source_project=standard_source_project,
        forced_copy_project_id=None,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        product_api_base_url="http://product.testserver.io",
        task_progress=task_progress,
    )

    # ASSERT
    spied_with_project_locked.assert_called_once()

    spied_with_project_locked.reset_mock()

    # ACT: cloning a TEMPLATE does NOT lock it (templates are not "in use")
    template_source_project = await _fetch_source_project(client.app, template_project["uuid"], logged_user["id"])
    await clone_project_data(
        client.app,
        source_project=template_source_project,
        forced_copy_project_id=None,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        product_api_base_url="http://product.testserver.io",
        task_progress=task_progress,
    )

    # ASSERT
    spied_with_project_locked.assert_not_called()


async def test_clone_project_data_with_template_parameters(
    client: TestClient,
    logged_user: UserInfoDict,
    template_project_with_params: ProjectDict,
    osparc_product_name: ProductName,
    task_progress: TaskProgress,
    mocked_dynamic_services_interface: dict[str, MockType],
    mock_dynamic_scheduler: None,
    storage_subsystem_mock_override: None,
):
    # SETUP
    assert client.app
    source_project = await _fetch_source_project(client.app, template_project_with_params["uuid"], logged_user["id"])

    # ACT
    cloned_project = await clone_project_data(
        client.app,
        source_project=source_project,
        forced_copy_project_id=None,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        product_api_base_url="http://product.testserver.io",
        task_progress=task_progress,
        template_parameters={"my_Na": "33", "my_BCL": "54.0"},
    )

    # ASSERT
    solver_node = next(
        node_data for node_data in cloned_project["workbench"].values() if node_data["label"].startswith("DBP-Clancy")
    )
    assert solver_node["inputs"]["Na"] == 33
    assert solver_node["inputs"]["BCL"] == 54.0

    # substitution also propagated into the DB-persisted project_nodes (not just the
    # in-memory workbench document)
    inserted_nodes = await _get_inserted_nodes(client.app, cloned_project["uuid"])
    solver_db_node = next(node for node in inserted_nodes.values() if node.label.startswith("DBP-Clancy"))
    assert solver_db_node.inputs["Na"] == 33
    assert solver_db_node.inputs["BCL"] == 54.0

    # port-link to the file-picker node was still remapped correctly
    file_picker_node_id = next(
        node_id for node_id, node_data in cloned_project["workbench"].items() if node_data["label"] == "File Picker 0D"
    )
    assert solver_node["inputs"]["initfile"]["nodeUuid"] == file_picker_node_id


async def test_clone_project_data_reports_progress(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: ProductName,
    task_progress: TaskProgress,
    mocked_dynamic_services_interface: dict[str, MockType],
    mock_dynamic_scheduler: None,
    storage_subsystem_mock_override: None,
):
    # SETUP
    assert client.app
    assert task_progress.percent == 0
    source_project = await _fetch_source_project(client.app, user_project["uuid"], logged_user["id"])

    # ACT
    await clone_project_data(
        client.app,
        source_project=source_project,
        forced_copy_project_id=None,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        product_api_base_url="http://product.testserver.io",
        task_progress=task_progress,
    )

    # ASSERT: `storage_subsystem_mock_override` yields a final progress of 1.0 (done=True)
    assert task_progress.percent == 1.0


#
# _clone_project_nodes (helper)
#


async def test_clone_project_nodes_remaps_port_links_and_input_nodes(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
):
    # SETUP
    assert client.app

    nodes_map: NodesMap = {
        NodeIDStr(node_id): NodeIDStr(f"11111111-1111-1111-1111-{i:012d}")
        for i, node_id in enumerate(user_project["workbench"])
    }

    # ACT
    cloned_nodes = await _clone_project_nodes(client.app, user_project, nodes_map)

    # ASSERT
    assert {f"{node_id}" for node_id in cloned_nodes} == set(nodes_map.values())
    for node_create in cloned_nodes.values():
        for input_node_id in node_create.input_nodes or []:
            assert input_node_id in nodes_map.values()
        for port_value in (node_create.inputs or {}).values():
            if isinstance(port_value, dict) and "nodeUuid" in port_value:
                assert port_value["nodeUuid"] in nodes_map.values()


#
# copy_allow_guests_to_push_states_and_output_ports
#


async def test_copy_allow_guests_to_push_states_and_output_ports_copies_flag_when_enabled(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    shared_project: ProjectDict,
):
    # SETUP
    assert client.app
    source_uuid = user_project["uuid"]
    destination_uuid = shared_project["uuid"]

    assert (
        await projects_repository.allows_guests_to_push_states_and_output_ports(client.app, project_uuid=source_uuid)
        is False
    )

    await projects_repository._set_allow_guests_to_push_states_and_output_ports(  # noqa: SLF001
        client.app, project_uuid=source_uuid
    )

    # ACT
    await copy_allow_guests_to_push_states_and_output_ports(
        client.app,
        from_project_uuid=source_uuid,
        to_project_uuid=destination_uuid,
    )

    # ASSERT
    assert (
        await projects_repository.allows_guests_to_push_states_and_output_ports(
            client.app, project_uuid=destination_uuid
        )
        is True
    )


async def test_copy_allow_guests_to_push_states_and_output_ports_keeps_disabled_when_source_disabled(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    shared_project: ProjectDict,
):
    # SETUP
    assert client.app
    source_uuid = user_project["uuid"]
    destination_uuid = shared_project["uuid"]

    assert (
        await projects_repository.allows_guests_to_push_states_and_output_ports(client.app, project_uuid=source_uuid)
        is False
    )

    # ACT
    await copy_allow_guests_to_push_states_and_output_ports(
        client.app,
        from_project_uuid=source_uuid,
        to_project_uuid=destination_uuid,
    )

    # ASSERT
    assert (
        await projects_repository.allows_guests_to_push_states_and_output_ports(
            client.app, project_uuid=destination_uuid
        )
        is False
    )
