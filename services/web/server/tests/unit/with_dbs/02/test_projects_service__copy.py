# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""Tests for the COPY project section of `_projects_service.py`:

- `clone_project_data` (shared clone primitive, also used by studies_dispatcher)
- `_clone_project_nodes` / `_remap_port_links_in_inputs` (helpers)
- `_copy_project_nodes_from_source_project` (`_crud_api_create.py`, project-copy route)
- `copy_allow_guests_to_push_states_and_output_ports`

NOTE: `clone_project_data` is meant to (in a future PR) replace part of the copy/clone
logic currently duplicated in `_crud_api_create.create_project`. The scenarios covered
here are inspired by the handler-level tests in `test_projects_crud_handlers.py`
(`test_new_project_from_template`, `test_new_project_from_other_study`,
`test_new_template_from_project`).
"""

import json
from collections.abc import Awaitable, Callable
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import UUID

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
from models_library.projects_nodes_io import NodeID, PortLink
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pytest_mock import MockerFixture, MockType
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.project_nodes_pricing import (
    R5_4XLARGE_NAME,
    get_node_pricing_state,
    make_pricing_unit,
    regex_for_rut_pricing_unit,
    resources_limits,
    set_node_pricing_link,
    set_node_required_resources,
    single_container_required_resources,
)
from pytest_simcore.helpers.webserver_projects import NewProject
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.projects import (
    _projects_repository as projects_repository,
)
from simcore_service_webserver.projects import _projects_service
from simcore_service_webserver.projects._crud_api_create import (
    _compose_project_data,
    _copy_project_nodes_from_source_project,
)
from simcore_service_webserver.projects._projects_repository_legacy import (
    ProjectDBAPI,
)
from simcore_service_webserver.projects._projects_service import (
    _clone_project_nodes,
    _remap_port_links_in_inputs,
    clone_project_data,
    copy_allow_guests_to_push_states_and_output_ports,
    raise_if_project_is_trashed,
)
from simcore_service_webserver.projects.exceptions import ProjectCopyingTrashedProjectError
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.projects.utils import NodesMap
from simcore_service_webserver.resource_usage.settings import (
    get_plugin_settings as get_rut_plugin_settings,
)
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = [
    "postgres",
    "redis",
    "rabbit",
]


@pytest.fixture
def app_environment(app_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    # the web-server takes ownership of a copied project's pricing state only in a product
    # that pays for computational resources; see the `billed_product` fixture
    monkeypatch.setenv("WEBSERVER_CREDIT_COMPUTATION_ENABLED", "1")
    return app_environment | {"WEBSERVER_CREDIT_COMPUTATION_ENABLED": "1"}


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


@pytest.fixture
async def project_with_simcore_file_links(
    client: TestClient,
    logged_user: UserInfoDict,
    fake_project: ProjectDict,
    osparc_product_name: ProductName,
    tests_data_dir: Path,
    faker: Faker,
):
    """Source project whose node inputs/outputs reference files in its own storage namespace.

    The file links are seeded as `{project_uuid}/{node_id}/outputs/output_1/parameters.json`,
    the shape a node's outputs get after a run, so the copy can be checked against the
    storage copy scheme `{destination_uuid}/{new_node_id}/{remainder}`.
    """
    assert client.app
    source_uuid = f"{faker.uuid4()}"
    solver_node = f"{faker.uuid4()}"
    consumer_node = f"{faker.uuid4()}"

    parameters_json = {
        "store": 0,
        "path": f"{source_uuid}/{solver_node}/outputs/output_1/parameters.json",
        "label": "parameters.json",
    }

    project_data = deepcopy(fake_project)
    project_data["uuid"] = source_uuid
    project_data["workbench"] = {
        solver_node: {
            "key": "simcore/services/comp/itis/sleeper",
            "version": "1.0.0",
            "label": "solver",
            "inputs": {},
            "outputs": {"output_1": parameters_json},
        },
        consumer_node: {
            "key": "simcore/services/dynamic/s4l-instance",
            "version": "2.0.0",
            "label": "s4l-instance",
            "inputs": {
                "input_1": deepcopy(parameters_json),
                "port_1": {"nodeUuid": solver_node, "output": "output_1"},
                "scalar": 3,
            },
            "outputs": {},
        },
    }

    async with NewProject(
        project_data,
        client.app,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        tests_data_dir=tests_data_dir,
        force_uuid=True,
    ) as project:
        assert project["uuid"] == source_uuid
        yield project


async def _get_inserted_nodes(app, project_uuid: str) -> dict[NodeID, Any]:
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)
    return {node.node_id: node for node in await db.list_project_nodes(ProjectID(project_uuid))}


async def _fetch_source_project(app, project_uuid: str, user_id: UserID) -> ProjectDict:
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
    nodes_map: NodesMap = {"old-node-id": "new-node-id"}
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
    old_node_id = UUID("38a0d401-af4b-4ea7-ab4c-5005c712a546")
    new_node_id = UUID("13220a1d-a569-49de-b375-904301af9295")
    nodes_map: NodesMap = {f"{old_node_id}": f"{new_node_id}"}
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
# raise_if_project_is_trashed
#


def test_raise_if_project_is_trashed_with_non_trashed_project(fake_project: ProjectDict):
    fake_project["trashed"] = None
    raise_if_project_is_trashed(fake_project)  # does not raise


def test_raise_if_project_is_trashed_with_trashed_project(fake_project: ProjectDict):
    fake_project["trashed"] = "2026-07-21T00:00:00+00:00"
    with pytest.raises(ProjectCopyingTrashedProjectError):
        raise_if_project_is_trashed(fake_project)


#
# clone_project_data
#


async def test_clone_project_data_raises_if_source_is_trashed(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: ProductName,
    task_progress: TaskProgress,
):
    assert client.app

    # SETUP: a trashed source project must never be duplicated
    source_project = await _fetch_source_project(client.app, user_project["uuid"], UserID(logged_user["id"]))
    source_project["trashed"] = "2026-07-21T00:00:00+00:00"

    # ACT & ASSERT
    with pytest.raises(ProjectCopyingTrashedProjectError):
        await clone_project_data(
            client.app,
            source_project=source_project,
            forced_copy_project_id=None,
            user_id=UserID(logged_user["id"]),
            product_name=osparc_product_name,
            product_api_base_url="http://product.testserver.io",
            task_progress=task_progress,
        )


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
    source_project = await _fetch_source_project(client.app, shared_project["uuid"], UserID(logged_user["id"]))
    assert len(source_project["accessRights"]) > 1

    # ACT
    cloned_project = await clone_project_data(
        client.app,
        source_project=source_project,
        forced_copy_project_id=None,
        user_id=UserID(logged_user["id"]),
        product_name=osparc_product_name,
        product_api_base_url="http://product.testserver.io",
        task_progress=task_progress,
    )

    # ASSERT
    # new project has a new uuid
    assert cloned_project["uuid"] != shared_project["uuid"]

    # access rights are reset to ONLY the new owner (stale collaborators from the
    # source project, e.g. `all_group`, are dropped)
    owner_gid = str(logged_user["primary_gid"])
    assert set(cloned_project["accessRights"].keys()) == {owner_gid}
    assert cloned_project["accessRights"][owner_gid] == {
        "read": True,
        "write": True,
        "delete": True,
    }

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
    source_project = await _fetch_source_project(client.app, user_project["uuid"], UserID(logged_user["id"]))

    # ACT
    cloned_project = await clone_project_data(
        client.app,
        source_project=source_project,
        forced_copy_project_id=forced_project_id,
        user_id=UserID(logged_user["id"]),
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
    standard_source_project = await _fetch_source_project(client.app, user_project["uuid"], UserID(logged_user["id"]))
    await clone_project_data(
        client.app,
        source_project=standard_source_project,
        forced_copy_project_id=None,
        user_id=UserID(logged_user["id"]),
        product_name=osparc_product_name,
        product_api_base_url="http://product.testserver.io",
        task_progress=task_progress,
    )

    # ASSERT
    spied_with_project_locked.assert_called_once()

    spied_with_project_locked.reset_mock()

    # ACT: cloning a TEMPLATE does NOT lock it (templates are not "in use")
    template_source_project = await _fetch_source_project(
        client.app, template_project["uuid"], UserID(logged_user["id"])
    )
    await clone_project_data(
        client.app,
        source_project=template_source_project,
        forced_copy_project_id=None,
        user_id=UserID(logged_user["id"]),
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
    source_project = await _fetch_source_project(
        client.app, template_project_with_params["uuid"], UserID(logged_user["id"])
    )

    # ACT
    cloned_project = await clone_project_data(
        client.app,
        source_project=source_project,
        forced_copy_project_id=None,
        user_id=UserID(logged_user["id"]),
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
    source_project = await _fetch_source_project(client.app, user_project["uuid"], UserID(logged_user["id"]))

    # ACT
    await clone_project_data(
        client.app,
        source_project=source_project,
        forced_copy_project_id=None,
        user_id=UserID(logged_user["id"]),
        product_name=osparc_product_name,
        product_api_base_url="http://product.testserver.io",
        task_progress=task_progress,
    )

    # ASSERT: `storage_subsystem_mock_override` yields a final progress of 1.0 (done=True)
    assert task_progress.percent == 1.0


async def test_clone_project_data_remaps_file_link_paths_in_persisted_nodes(
    client: TestClient,
    logged_user: UserInfoDict,
    project_with_simcore_file_links: ProjectDict,
    osparc_product_name: ProductName,
    task_progress: TaskProgress,
    mocked_dynamic_services_interface: dict[str, MockType],
    mock_dynamic_scheduler: None,
    storage_subsystem_mock_override: None,
):
    # SETUP
    assert client.app
    source_project = await _fetch_source_project(
        client.app, project_with_simcore_file_links["uuid"], UserID(logged_user["id"])
    )

    # ACT
    cloned_project = await clone_project_data(
        client.app,
        source_project=source_project,
        forced_copy_project_id=None,
        user_id=UserID(logged_user["id"]),
        product_name=osparc_product_name,
        product_api_base_url="http://product.testserver.io",
        task_progress=task_progress,
    )

    # ASSERT: the persisted nodes reference the clone's own storage namespace, matching
    # where the data-copy relocates the files
    inserted_nodes = await _get_inserted_nodes(client.app, cloned_project["uuid"])
    solver_node = next(node for node in inserted_nodes.values() if node.label == "solver")
    consumer_node = next(node for node in inserted_nodes.values() if node.label == "s4l-instance")

    expected_path = f"{cloned_project['uuid']}/{solver_node.node_id}/outputs/output_1/parameters.json"
    assert solver_node.outputs["output_1"]["path"] == expected_path
    assert consumer_node.inputs["input_1"]["path"] == expected_path
    assert consumer_node.inputs["port_1"]["nodeUuid"] == f"{solver_node.node_id}"
    assert consumer_node.inputs["scalar"] == 3


#
# _clone_project_nodes (helper)
#


async def test_clone_project_nodes_remaps_port_links_and_input_nodes(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    faker: Faker,
):
    # SETUP
    assert client.app

    nodes_map: NodesMap = {
        node_id: f"11111111-1111-1111-1111-{i:012d}" for i, node_id in enumerate(user_project["workbench"])
    }

    # ACT
    cloned_nodes = await _clone_project_nodes(
        client.app, user_project, nodes_map, destination_project_uuid=f"{faker.uuid4()}"
    )

    # ASSERT
    assert {f"{node_id}" for node_id in cloned_nodes} == set(nodes_map.values())
    for node_create in cloned_nodes.values():
        for input_node_id in node_create.input_nodes or []:
            assert input_node_id in nodes_map.values()
        for port_value in (node_create.inputs or {}).values():
            if isinstance(port_value, dict) and "nodeUuid" in port_value:
                assert port_value["nodeUuid"] in nodes_map.values()


async def test_clone_project_nodes_remaps_file_link_paths(
    client: TestClient,
    project_with_simcore_file_links: ProjectDict,
    faker: Faker,
):
    # SETUP
    assert client.app
    source_project = project_with_simcore_file_links
    source_uuid = source_project["uuid"]
    solver_node = next(node_id for node_id, data in source_project["workbench"].items() if data["label"] == "solver")
    consumer_node = next(
        node_id for node_id, data in source_project["workbench"].items() if data["label"] == "s4l-instance"
    )
    nodes_map: NodesMap = {node_id: f"{faker.uuid4()}" for node_id in source_project["workbench"]}
    destination_uuid = f"{faker.uuid4()}"

    # ACT
    cloned_nodes = await _clone_project_nodes(
        client.app, source_project, nodes_map, destination_project_uuid=destination_uuid
    )

    # ASSERT: file links follow the storage copy scheme {destination}/{new_node}/{remainder}
    expected_path = f"{destination_uuid}/{nodes_map[solver_node]}/outputs/output_1/parameters.json"
    solver_outputs = cloned_nodes[NodeID(nodes_map[solver_node])].outputs or {}
    assert solver_outputs["output_1"]["path"] == expected_path
    consumer_inputs = cloned_nodes[NodeID(nodes_map[consumer_node])].inputs or {}
    assert consumer_inputs["input_1"]["path"] == expected_path
    assert consumer_inputs["port_1"]["nodeUuid"] == nodes_map[solver_node]
    assert consumer_inputs["scalar"] == 3

    # the source project rows are left untouched
    source_nodes = await _get_inserted_nodes(client.app, source_uuid)
    assert source_nodes[NodeID(solver_node)].outputs["output_1"]["path"].startswith(f"{source_uuid}/")


async def test_copy_project_nodes_from_source_project_remaps_file_links_only_on_deep_copy(
    client: TestClient,
    project_with_simcore_file_links: ProjectDict,
    faker: Faker,
):
    # SETUP
    assert client.app
    source_project = project_with_simcore_file_links
    source_uuid = source_project["uuid"]
    solver_node = next(node_id for node_id, data in source_project["workbench"].items() if data["label"] == "solver")
    consumer_node = next(
        node_id for node_id, data in source_project["workbench"].items() if data["label"] == "s4l-instance"
    )
    nodes_map: NodesMap = {node_id: f"{faker.uuid4()}" for node_id in source_project["workbench"]}
    destination_uuid = f"{faker.uuid4()}"
    source_path = f"{source_uuid}/{solver_node}/outputs/output_1/parameters.json"

    # ACT: deep copy — the storage copy transfers the bytes, links must follow the copies
    deep_nodes = await _copy_project_nodes_from_source_project(
        client.app,
        source_project,
        nodes_map,
        clean_output_data=False,
        destination_project_uuid=destination_uuid,
    )

    # ASSERT
    expected_path = f"{destination_uuid}/{nodes_map[solver_node]}/outputs/output_1/parameters.json"
    assert (deep_nodes[NodeID(nodes_map[solver_node])].outputs or {})["output_1"]["path"] == expected_path
    deep_consumer_inputs = deep_nodes[NodeID(nodes_map[consumer_node])].inputs or {}
    assert deep_consumer_inputs["input_1"]["path"] == expected_path

    # ACT: shallow copy — no data is transferred, links keep pointing at the source files
    shallow_nodes = await _copy_project_nodes_from_source_project(
        client.app,
        source_project,
        nodes_map,
        clean_output_data=True,
        destination_project_uuid=destination_uuid,
    )

    # ASSERT
    assert (shallow_nodes[NodeID(nodes_map[solver_node])].outputs or {}) == {}
    shallow_consumer_inputs = shallow_nodes[NodeID(nodes_map[consumer_node])].inputs or {}
    assert shallow_consumer_inputs["input_1"]["path"] == source_path


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


#
# CHARACTERIZATION TESTS (pin the state of the DB, not the code that produces it)
#


# hand-computed: a computational node sized for r5.4xlarge (16 CPU / 128 GiB)
# with the DASK-WORKER formula: cpu = 16 - 0.1 = 15.9,
#                              ram = int(128 GiB * 0.9) = 123695058124
_SOURCED_SIZED_RESOURCES: dict[str, Any] = single_container_required_resources(
    "simcore/services/comp/itis/sleeper", cpu=15.9, ram_bytes=123695058124
)
_PRICING_PLAN_ID = 1
_PRICING_UNIT_ID = 2

# the DEFAULT unit mocked by `mock_rut_default_pricing_unit` (t3.medium):
# hand-computed dask-worker sizing: cpu = 2.0 - 0.1 = 1.9, ram = int(4 GiB * 0.9) = 3865470566
_DEFAULT_PRICING_PLAN_ID = 1
_DEFAULT_PRICING_UNIT_ID = 1


def _sleeper_node(nodes: dict) -> Any:
    # the workbench fixture has TWO comp sleepers; pin one deterministically by label
    return next(node for node in nodes.values() if node.label == "sleeper")


async def _price_and_size_one_computational_node(
    app, engine: AsyncEngine, project_uuid: str
) -> tuple[str, dict[str, Any]]:
    """Directly (no endpoints) give the project's computational node a non-default
    pricing-unit link and hand-sized `required_resources`.
    """
    nodes = await _get_inserted_nodes(app, project_uuid)
    comp_node = _sleeper_node(nodes)
    await set_node_pricing_link(
        engine,
        project_uuid,
        f"{comp_node.node_id}",
        pricing_plan_id=_PRICING_PLAN_ID,
        pricing_unit_id=_PRICING_UNIT_ID,
    )
    await set_node_required_resources(engine, project_uuid, f"{comp_node.node_id}", _SOURCED_SIZED_RESOURCES)
    return f"{comp_node.node_id}", _SOURCED_SIZED_RESOURCES


async def _assert_clone_pricing_state(
    app, engine: AsyncEngine, cloned_project: ProjectDict, expected_resources: dict[str, Any]
) -> None:
    state = await get_node_pricing_state(engine, cloned_project["uuid"])
    assert len(state) == len(cloned_project["workbench"])
    nodes = await _get_inserted_nodes(app, cloned_project["uuid"])

    # the source's pricing link is copied (validated against this product) and the
    # source's hand-sized `required_resources` are kept verbatim — NOT re-sized
    comp_node = _sleeper_node(nodes)
    priced_state = state[comp_node.node_id]
    assert priced_state.pricing_plan_id == _PRICING_PLAN_ID
    assert priced_state.pricing_unit_id == _PRICING_UNIT_ID
    assert priced_state.required_resources == expected_resources

    # a computational node without a source link gets the DEFAULT unit and is
    # sized with the dask-worker formula of that unit's machine
    second_comp_node = next(node for node in nodes.values() if node.label == "sleeper_2")
    default_state = state[second_comp_node.node_id]
    assert default_state.pricing_plan_id == _DEFAULT_PRICING_PLAN_ID
    assert default_state.pricing_unit_id == _DEFAULT_PRICING_UNIT_ID
    # sizing rewrites the resources and keeps the rest of the payload (image...)
    assert default_state.required_resources
    sized = default_state.required_resources["container"]["resources"]
    assert sized == resources_limits(cpu=1.9, ram_bytes=3865470566)

    # frontend nodes get no link
    for node in nodes.values():
        if f"{node.key}".startswith("simcore/services/frontend/"):
            node_state = state[node.node_id]
            assert node_state.pricing_plan_id is None
            assert node_state.pricing_unit_id is None


@pytest.mark.parametrize("source_kind", ["standard_project", "template"])
async def test_clone_project_data_copies_pricing_links_and_sizes_unlinked_comp_nodes(
    source_kind: str,
    *,
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    template_project: ProjectDict,
    osparc_product_name: ProductName,
    task_progress: TaskProgress,
    mocked_dynamic_services_interface: dict[str, MockType],
    mock_dynamic_scheduler: None,
    storage_subsystem_mock_override: None,
    sqlalchemy_async_engine: AsyncEngine,
    aioresponses_mocker: AioResponsesMock,
    mock_rut_default_pricing_unit: None,
    mocked_director_v2_node_sizing: MockType,
    billed_product: None,
):
    """W6/W7: cloning (a project or a template) in a BILLED product copies the source
    pricing links (validated against the destination product) and keeps the source
    `required_resources` verbatim. A computational node WITHOUT a source link gets the
    DEFAULT unit and is sized with its machine's dask-worker formula. Frontend nodes keep
    no link.
    """
    assert client.app
    source = template_project if source_kind == "template" else user_project
    source_uuid = source["uuid"]

    # SETUP: source computational node is linked to a non-default unit and sized
    _, sourced_resources = await _price_and_size_one_computational_node(
        client.app, sqlalchemy_async_engine, source_uuid
    )

    # RUT knows the source's non-default unit (copy validation asks for it)
    settings = get_rut_plugin_settings(client.app)
    aioresponses_mocker.get(
        regex_for_rut_pricing_unit(f"{settings.api_base_url}", _PRICING_PLAN_ID, _PRICING_UNIT_ID),
        payload=jsonable_encoder(
            make_pricing_unit(
                pricing_unit_id=_PRICING_UNIT_ID,
                default=False,
                aws_ec2_instance=R5_4XLARGE_NAME,
            )
        ),
        repeat=True,
    )

    # ACT
    source_project = await _fetch_source_project(client.app, source_uuid, UserID(logged_user["id"]))
    cloned_project = await clone_project_data(
        client.app,
        source_project=source_project,
        forced_copy_project_id=None,
        user_id=UserID(logged_user["id"]),
        product_name=osparc_product_name,
        product_api_base_url="http://product.testserver.io",
        task_progress=task_progress,
    )

    # only the newly default-linked computational node is sized (the copied link
    # keeps the source's resources verbatim)
    mocked_director_v2_node_sizing.assert_called_once()

    # ASSERT: the clone's DB state
    await _assert_clone_pricing_state(client.app, sqlalchemy_async_engine, cloned_project, sourced_resources)

    # the SOURCE project keeps its link and resources untouched
    source_state = await get_node_pricing_state(sqlalchemy_async_engine, source_uuid)
    linked = {
        node_id: node_state for node_id, node_state in source_state.items() if node_state.pricing_unit_id is not None
    }
    assert len(linked) == 1
    (source_node_state,) = linked.values()
    assert source_node_state.pricing_plan_id == _PRICING_PLAN_ID
    assert source_node_state.required_resources == sourced_resources


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


@pytest.mark.parametrize(
    "tracker_answer, copied_link",
    [
        pytest.param(
            {
                "payload": jsonable_encoder(
                    make_pricing_unit(pricing_unit_id=_PRICING_UNIT_ID, default=False, aws_ec2_instance=R5_4XLARGE_NAME)
                )
            },
            (_PRICING_PLAN_ID, _PRICING_UNIT_ID),
            id="the product knows the unit",
        ),
        pytest.param({"status": status.HTTP_404_NOT_FOUND}, (None, None), id="unknown in the product"),
        pytest.param({"status": status.HTTP_503_SERVICE_UNAVAILABLE}, (_PRICING_PLAN_ID, _PRICING_UNIT_ID), id="503"),
        pytest.param({"exception": TimeoutError}, (_PRICING_PLAN_ID, _PRICING_UNIT_ID), id="no answer"),
    ],
)
async def test_copy_pricing_links_asks_the_tracker_once_per_unit_and_copies_what_it_can(
    tracker_answer: dict[str, Any],
    copied_link: tuple[int | None, int | None],
    client: TestClient,
    user_project: ProjectDict,
    shared_project: ProjectDict,
    osparc_product_name: ProductName,
    sqlalchemy_async_engine: AsyncEngine,
    aioresponses_mocker: AioResponsesMock,
    mocker: MockerFixture,
    billed_product: None,
):
    """Several nodes of a project typically share one pricing unit: the copy asks the
    resource-usage-tracker about every DISTINCT plan/unit once, not once per node, which
    an unreachable tracker would otherwise pay for with one timeout per node. A unit the
    product does not know is not copied (the caller links the destination's default
    instead); one it could not confirm is copied rather than lost, and the copy succeeds
    either way.
    """
    assert client.app
    # both projects were inserted from the same workbench, so their node ids match
    nodes_map: NodesMap = {
        node_id: node_id for node_id, node in user_project["workbench"].items() if "/comp/" in node["key"]
    }
    assert len(nodes_map) > 1

    for node_id in nodes_map:
        await set_node_pricing_link(
            sqlalchemy_async_engine,
            user_project["uuid"],
            node_id,
            pricing_plan_id=_PRICING_PLAN_ID,
            pricing_unit_id=_PRICING_UNIT_ID,
        )
    settings = get_rut_plugin_settings(client.app)
    aioresponses_mocker.get(
        regex_for_rut_pricing_unit(f"{settings.api_base_url}", _PRICING_PLAN_ID, _PRICING_UNIT_ID),
        repeat=True,
        **tracker_answer,
    )
    validate_link = mocker.spy(_projects_service.rut_api, "get_pricing_plan_unit")

    await _projects_service.copy_pricing_links(
        client.app,
        source_project_id=ProjectID(user_project["uuid"]),
        destination_project_id=ProjectID(shared_project["uuid"]),
        nodes_map=nodes_map,
        product_name=osparc_product_name,
    )

    # one request for the distinct plan/unit, failures memoized like successes
    assert validate_link.call_count == 1
    destination_state = await get_node_pricing_state(sqlalchemy_async_engine, shared_project["uuid"])
    for node_id in nodes_map:
        node_state = destination_state[NodeID(node_id)]
        assert (node_state.pricing_plan_id, node_state.pricing_unit_id) == copied_link


async def test_copy_pricing_links_copies_nothing_in_a_product_that_does_not_bill(
    client: TestClient,
    user_project: ProjectDict,
    shared_project: ProjectDict,
    osparc_product_name: ProductName,
    sqlalchemy_async_engine: AsyncEngine,
    aioresponses_mocker: AioResponsesMock,
    mocker: MockerFixture,
):
    """Copying in a product that does not pay for computational resources copies no
    pricing link, which is what keeps the copied nodes' resources writable through
    `PUT .../nodes/{node_id}/resources`. The tracker is not asked about anything.
    """
    assert client.app
    nodes_map: NodesMap = {
        node_id: node_id for node_id, node in user_project["workbench"].items() if "/comp/" in node["key"]
    }
    for node_id in nodes_map:
        await set_node_pricing_link(
            sqlalchemy_async_engine,
            user_project["uuid"],
            node_id,
            pricing_plan_id=_PRICING_PLAN_ID,
            pricing_unit_id=_PRICING_UNIT_ID,
        )
    ask_tracker = mocker.spy(_projects_service.rut_api, "get_pricing_plan_unit")

    await _projects_service.copy_pricing_links(
        client.app,
        source_project_id=ProjectID(user_project["uuid"]),
        destination_project_id=ProjectID(shared_project["uuid"]),
        nodes_map=nodes_map,
        product_name=osparc_product_name,
    )

    ask_tracker.assert_not_called()
    destination_state = await get_node_pricing_state(sqlalchemy_async_engine, shared_project["uuid"])
    for node_id in nodes_map:
        node_state = destination_state[NodeID(node_id)]
        assert node_state.pricing_plan_id is None
        assert node_state.pricing_unit_id is None


async def test_a_link_copied_during_a_tracker_outage_is_repaired_on_the_next_billed_start(
    *,
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: ProductName,
    task_progress: TaskProgress,
    mocked_dynamic_services_interface: dict[str, MockType],
    mock_dynamic_scheduler: None,
    storage_subsystem_mock_override: None,
    sqlalchemy_async_engine: AsyncEngine,
    aioresponses_mocker: AioResponsesMock,
    mock_rut_default_pricing_unit: None,
    mocked_director_v2_node_sizing: MockType,
    billed_product: None,
):
    """Copying while the tracker is unreachable keeps the source's link and the resources
    sized for it, so the copy costs nothing it cannot recover. If that link turns out not
    to exist in the destination product, the next billed start replaces it with the
    destination's default unit and sizes the node for it, instead of leaving the node
    unusable for every run.
    """
    assert client.app
    source_uuid = user_project["uuid"]
    _, sourced_resources = await _price_and_size_one_computational_node(
        client.app, sqlalchemy_async_engine, source_uuid
    )
    settings = get_rut_plugin_settings(client.app)
    source_link_url = regex_for_rut_pricing_unit(f"{settings.api_base_url}", _PRICING_PLAN_ID, _PRICING_UNIT_ID)
    # unreachable during the copy, and unknown in this product afterwards
    aioresponses_mocker.get(source_link_url, exception=TimeoutError)
    aioresponses_mocker.get(source_link_url, status=status.HTTP_404_NOT_FOUND, repeat=True)

    source_project = await _fetch_source_project(client.app, source_uuid, UserID(logged_user["id"]))
    cloned_project = await clone_project_data(
        client.app,
        source_project=source_project,
        forced_copy_project_id=None,
        user_id=UserID(logged_user["id"]),
        product_name=osparc_product_name,
        product_api_base_url="http://product.testserver.io",
        task_progress=task_progress,
    )
    cloned_uuid = ProjectID(cloned_project["uuid"])
    copied_node_id = f"{_sleeper_node(await _get_inserted_nodes(client.app, f'{cloned_uuid}')).node_id}"

    # the copy kept the link it could not confirm, and the resources sized for it
    state = await get_node_pricing_state(sqlalchemy_async_engine, cloned_uuid)
    copied = state[NodeID(copied_node_id)]
    assert copied.pricing_plan_id == _PRICING_PLAN_ID
    assert copied.pricing_unit_id == _PRICING_UNIT_ID
    assert copied.required_resources == sourced_resources

    await _projects_service.repair_projects_nodes_pricing_and_resources(
        client.app,
        user_id=UserID(logged_user["id"]),
        project_ids=[cloned_uuid],
        product_name=osparc_product_name,
    )

    # the next billed start replaces the link the product does not know, and sizes for the
    # unit it links instead
    state = await get_node_pricing_state(sqlalchemy_async_engine, cloned_uuid)
    repaired = state[NodeID(copied_node_id)]
    assert repaired.pricing_plan_id == _DEFAULT_PRICING_PLAN_ID
    assert repaired.pricing_unit_id == _DEFAULT_PRICING_UNIT_ID
    assert repaired.required_resources
    assert repaired.required_resources["container"]["resources"] == resources_limits(cpu=1.9, ram_bytes=3865470566)


async def test_compose_project_data_of_a_copy_says_nothing_about_the_nodes(
    client: TestClient,
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    faker: Faker,
):
    """Overriding fields of a copy (its name, e.g. when an api-server job renames it)
    must not replace the nodes prepared from the source project: the caller keeps the
    source's `required_resources` (and the pricing links copied on top of them).
    """
    assert client.app
    new_project, project_nodes = await _compose_project_data(
        client.app,
        user_id=UserID(logged_user["id"]),
        product_name=osparc_product_name,
        new_project={"uuid": f"{faker.uuid4()}", "name": "copy of source", "description": "from the source"},
        predefined_project={"name": "renamed copy", "description": None},
    )

    assert project_nodes is None
    assert new_project["name"] == "renamed copy"
    # a field the override leaves empty keeps the source project's value
    assert new_project["description"] == "from the source"


async def test_creating_a_copy_with_a_name_override_through_the_endpoint_keeps_the_priced_nodes(
    *,
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group: dict[str, str],
    user_project: ProjectDict,
    sqlalchemy_async_engine: AsyncEngine,
    aioresponses_mocker: AioResponsesMock,
    storage_subsystem_mock: Any,
    project_db_cleaner: None,
    mocked_dynamic_services_interface: dict[str, MockType],
    mock_dynamic_scheduler: None,
    mock_rut_default_pricing_unit: None,
    mocked_director_v2_node_sizing: MockType,
    billed_product: None,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
):
    """The same override through `POST /v0/projects?from_study=...`: a body that renames the
    copy says nothing about its nodes, so the copy carries the source's pricing link and the
    resources sized for it, on one node row per source node.
    """
    assert client.app
    _, sourced_resources = await _price_and_size_one_computational_node(
        client.app, sqlalchemy_async_engine, user_project["uuid"]
    )
    settings = get_rut_plugin_settings(client.app)
    aioresponses_mocker.get(
        regex_for_rut_pricing_unit(f"{settings.api_base_url}", _PRICING_PLAN_ID, _PRICING_UNIT_ID),
        payload=jsonable_encoder(
            make_pricing_unit(pricing_unit_id=_PRICING_UNIT_ID, default=False, aws_ec2_instance=R5_4XLARGE_NAME)
        ),
        repeat=True,
    )

    new_project = await request_create_project(
        client,
        status.HTTP_202_ACCEPTED,
        status.HTTP_201_CREATED,
        logged_user,
        primary_group,
        project={"name": "renamed copy"},
        from_study=user_project,
        copy_data=False,
    )

    assert new_project["name"] == "renamed copy"
    state = await get_node_pricing_state(sqlalchemy_async_engine, new_project["uuid"])
    assert len(state) == len(new_project["workbench"])

    copied_link = [node_state for node_state in state.values() if node_state.pricing_unit_id == _PRICING_UNIT_ID]
    assert len(copied_link) == 1
    (copied,) = copied_link
    assert copied.pricing_plan_id == _PRICING_PLAN_ID
    assert copied.required_resources == sourced_resources
