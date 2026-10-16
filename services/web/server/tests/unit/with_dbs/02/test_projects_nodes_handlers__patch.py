# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-statements


import asyncio
import json
from http import HTTPStatus
from unittest import mock

import pytest
from aiohttp.test_utils import TestClient
from deepdiff import DeepDiff
from models_library.projects_nodes import PartialNode
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.postgres_locks import TIMEOUT_S, count_lock_waiters_behind, get_backend_pid, wait_until
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from servicelib.rabbitmq.rpc_interfaces.catalog.errors import (
    CatalogForbiddenRpcError,
    CatalogItemNotFoundRpcError,
)
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects import (
    _projects_nodes_repository as projects_nodes_repository,
)
from simcore_service_webserver.projects import _projects_repository as projects_repository
from simcore_service_webserver.projects import _projects_service as projects_service
from simcore_service_webserver.projects.models import ProjectDict
from sqlalchemy.ext.asyncio import AsyncEngine

API_PREFIX = "/" + api_version_prefix


@pytest.fixture
def mock_catalog_rpc_check_for_service(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_webserver.projects._projects_service.catalog_rpc.check_for_service",
        spec=True,
        return_value=True,
    )


@pytest.fixture
def mocked_notify_project_node_update(mocker: MockerFixture):
    return mocker.patch(
        "simcore_service_webserver.projects._projects_service.notify_project_node_update",
    )


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_204_NO_CONTENT),
        (UserRole.USER, status.HTTP_204_NO_CONTENT),
        (UserRole.TESTER, status.HTTP_204_NO_CONTENT),
        (UserRole.ADMIN, status.HTTP_204_NO_CONTENT),
        (UserRole.PRODUCT_OWNER, status.HTTP_204_NO_CONTENT),
    ],
)
async def test_patch_project_node_entrypoint_access(
    mock_dynamic_scheduler: None,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
):
    node_id = next(iter(user_project["workbench"]))
    assert client.app
    base_url = client.app.router["patch_project_node"].url_for(project_id=user_project["uuid"], node_id=node_id)
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps({"label": "testing-string"}),
    )
    await assert_status(resp, expected)


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_204_NO_CONTENT)])
async def test_patch_project_node(
    mock_dynamic_scheduler: None,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mock_catalog_rpc_check_for_service: None,
):
    node_id = next(iter(user_project["workbench"]))
    sibling_node_id = next(candidate for candidate in user_project["workbench"] if candidate != node_id)
    assert client.app
    base_url = client.app.router["patch_project_node"].url_for(project_id=user_project["uuid"], node_id=node_id)
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps({"label": "testing-string", "progress": None, "something": "non-existing"}),
    )
    await assert_status(resp, expected)
    # service key
    _patch_key = {"key": "simcore/services/dynamic/patch-service-key"}
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(_patch_key),
    )
    await assert_status(resp, expected)
    # service version
    _patch_version = {"version": "2.0.9"}
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(_patch_version),
    )
    await assert_status(resp, expected)
    # inputs
    _patch_inputs = {
        "inputs": {
            "input_3": 0.0,
            "input_2": 3.0,
            "input_1": {
                "store": 0,
                "path": "api/eddb9098-ac99-331e-930e-d77e25ffe633/file_with_number.txt",
                "label": "file_with_number.txt",
                "eTag": "eccbc87e4b5ce2fe28308fd9f2a7baf3",
                "dataset": None,
            },
        }
    }
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(_patch_inputs),
    )
    await assert_status(resp, expected)
    # inputs required
    _patch_inputs_required = {
        "inputsRequired": [
            "input_1",
            "input_3",
        ]
    }
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(_patch_inputs_required),
    )
    await assert_status(resp, expected)
    # input nodes
    _patch_input_nodes = {
        "inputNodes": [
            sibling_node_id,
        ]
    }
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(_patch_input_nodes),
    )
    await assert_status(resp, expected)
    # boot_options
    _patch_boot_options = {"bootOptions": {"boot_mode": "1"}}
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(_patch_boot_options),
    )
    await assert_status(resp, expected)
    # outputs
    _patch_outputs = {
        "outputs": {
            "output_1": {
                "store": 0,
                "path": "9934cba6-4b51-11ef-968a-02420a00f1c1/571ffc8d-fa6e-411f-afc8-9c62d08dd2fa/matus.txt",
                "label": "matus.txt",
                "eTag": "d41d8cd98f00b204e9800998ecf8427e",
                "dataset": None,
            }
        }
    }
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(_patch_outputs),
    )
    await assert_status(resp, expected)
    # ui
    _patch_ui = {"ui": {"position": {"x": 10, "y": 20}, "marker": {"color": "#123456"}}}
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(_patch_ui),
    )
    await assert_status(resp, expected)
    # ui partial patch: only `position` is sent, the previously set `marker` must be preserved (merge semantics)
    _patch_ui_position = {"ui": {"position": {"x": 33, "y": 44}}}
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(_patch_ui_position),
    )
    await assert_status(resp, expected)
    _expected_ui = {"position": {"x": 33, "y": 44}, "marker": {"color": "#123456"}}

    # Get project
    get_url = client.app.router["get_project"].url_for(project_id=user_project["uuid"])
    resp = await client.get(f"{get_url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    _tested_node = data["workbench"][node_id]

    assert _tested_node["label"] == "testing-string"
    assert _tested_node["key"] == _patch_key["key"]
    assert _tested_node["version"] == _patch_version["version"]
    assert _tested_node["inputs"] == _patch_inputs["inputs"]
    assert _tested_node["inputsRequired"] == _patch_inputs_required["inputsRequired"]
    assert _tested_node["inputNodes"] == _patch_input_nodes["inputNodes"]
    assert _tested_node["bootOptions"] == _patch_boot_options["bootOptions"]
    assert _tested_node["outputs"] == _patch_outputs["outputs"]
    assert not DeepDiff(_tested_node["ui"], _expected_ui)


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_204_NO_CONTENT)])
async def test_patch_project_node_ui_remove_marker(
    mock_dynamic_scheduler: None,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mock_catalog_rpc_check_for_service: None,
):
    node_id = next(iter(user_project["workbench"]))
    assert client.app
    base_url = client.app.router["patch_project_node"].url_for(project_id=user_project["uuid"], node_id=node_id)

    # set both position and marker
    _patch_ui = {"ui": {"position": {"x": 10, "y": 20}, "marker": {"color": "#123456"}}}
    resp = await client.patch(f"{base_url}", data=json.dumps(_patch_ui))
    await assert_status(resp, expected)

    # remove the marker by sending `marker: null`, `position` must be preserved (merge semantics)
    _patch_remove_marker = {"ui": {"marker": None}}
    resp = await client.patch(f"{base_url}", data=json.dumps(_patch_remove_marker))
    await assert_status(resp, expected)

    get_url = client.app.router["get_project"].url_for(project_id=user_project["uuid"])
    resp = await client.get(f"{get_url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    _tested_node_ui = data["workbench"][node_id]["ui"]

    assert _tested_node_ui["position"] == {"x": 10, "y": 20}
    # the marker key must be removed from the stored ui, not persisted as null
    assert "marker" not in _tested_node_ui


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_204_NO_CONTENT)])
@pytest.mark.parametrize(
    "patch_payload,expect_pipeline_sync",
    [
        pytest.param({"progress": 42.0}, False, id="progress only"),
        pytest.param({"progress": 100.0}, False, id="progress finished"),
        pytest.param({"ui": {"position": {"x": 1, "y": 2}}}, False, id="ui only"),
        pytest.param({"progress": 12.5, "ui": {"marker": {"color": "#123456"}}}, False, id="progress and ui"),
        pytest.param({"progress": 42.0, "label": "renamed"}, True, id="progress with label"),
        pytest.param({"label": "renamed"}, True, id="label only"),
    ],
)
async def test_patch_project_node_syncs_director_v2_only_for_non_ui_keys(
    mock_dynamic_scheduler: None,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mock_catalog_rpc_check_for_service: None,
    patch_payload: dict,
    expect_pipeline_sync: bool,
):
    """patches touching only keys director-v2 does not use (see _NODE_UI_KEYS) must not
    trigger a pipeline sync, since the file-picker progress updates would otherwise
    fire a full POST /v2/computations on every tick
    """
    node_id = next(iter(user_project["workbench"]))
    assert client.app
    base_url = client.app.router["patch_project_node"].url_for(project_id=user_project["uuid"], node_id=node_id)

    resp = await client.patch(f"{base_url}", json=patch_payload)
    await assert_status(resp, expected)

    create_or_update_pipeline = mocked_dynamic_services_interface["director_v2.api.create_or_update_pipeline"]
    if expect_pipeline_sync:
        create_or_update_pipeline.assert_called_once()
    else:
        create_or_update_pipeline.assert_not_called()


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_204_NO_CONTENT)])
async def test_patch_computational_project_node_notifies_only_updated_node(
    mock_dynamic_scheduler: None,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mocked_notify_project_node_update,
):
    node_id = next(node_id for node_id, node in user_project["workbench"].items() if "/comp/" in node["key"])
    assert client.app
    base_url = client.app.router["patch_project_node"].url_for(project_id=user_project["uuid"], node_id=node_id)

    resp = await client.patch(f"{base_url}", json={"label": "updated label", "runHash": None})

    await assert_status(resp, expected)
    mocked_notify_project_node_update.assert_awaited_once()
    # REST-triggered notifications are not strict (only the outbox consumer is)
    assert not mocked_notify_project_node_update.await_args.kwargs.get("strict", False)
    notified_project = mocked_notify_project_node_update.await_args.args[1]
    assert set(notified_project["workbench"]) == {node_id}
    assert notified_project["workbench"][node_id]["label"] == "updated label"
    assert notified_project["workbench"][node_id]["runHash"] is None


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_204_NO_CONTENT)])
async def test_patch_project_node_notifies_outputs_updated_during_pipeline_sync(
    mock_dynamic_scheduler: None,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mocked_notify_project_node_update,
):
    node_id = next(node_id for node_id, node in user_project["workbench"].items() if "/comp/" in node["key"])
    assert client.app
    base_url = client.app.router["patch_project_node"].url_for(project_id=user_project["uuid"], node_id=node_id)
    outputs_updated_during_pipeline_sync = {"output_1": 42}

    async def _update_outputs_during_pipeline_sync(*args: object, **kwargs: object) -> None:
        await projects_nodes_repository.update(
            client.app,
            project_id=user_project["uuid"],
            node_id=node_id,
            partial_node=PartialNode.model_construct(outputs=outputs_updated_during_pipeline_sync),
        )

    mocked_dynamic_services_interface[
        "director_v2.api.create_or_update_pipeline"
    ].side_effect = _update_outputs_during_pipeline_sync

    resp = await client.patch(f"{base_url}", json={"label": "updated label"})

    await assert_status(resp, expected)
    mocked_notify_project_node_update.assert_awaited_once()
    # REST-triggered notifications are not strict (only the outbox consumer is)
    assert not mocked_notify_project_node_update.await_args.kwargs.get("strict", False)
    notified_project = mocked_notify_project_node_update.await_args.args[1]
    assert notified_project["workbench"][node_id]["outputs"] == outputs_updated_during_pipeline_sync


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_204_NO_CONTENT)])
async def test_patch_project_node_notifies(
    mocker: MockerFixture,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mock_catalog_rpc_check_for_service,
    mocked_notify_project_node_update,
):
    node_id = next(iter(user_project["workbench"]))
    assert client.app
    base_url = client.app.router["patch_project_node"].url_for(project_id=user_project["uuid"], node_id=node_id)

    # inputs
    _patch_inputs = {
        "key": "simcore/services/dynamic/patch-service-key",
    }
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(_patch_inputs),
    )
    await assert_status(resp, expected)
    assert mocked_notify_project_node_update.call_count == 1
    args = mocked_notify_project_node_update.await_args_list
    assert args[0][0][1]["workbench"][node_id]["key"] == _patch_inputs["key"]
    assert f"{args[0][0][2]}" == node_id


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_204_NO_CONTENT)])
async def test_patch_project_node_inputs_notifies(
    mocker: MockerFixture,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
):
    node_id = next(iter(user_project["workbench"]))
    sibling_node_id = next(candidate for candidate in user_project["workbench"] if candidate != node_id)
    assert client.app
    base_url = client.app.router["patch_project_node"].url_for(project_id=user_project["uuid"], node_id=node_id)
    notify_project_nodes_update = mocker.spy(projects_service, "notify_project_nodes_update")
    list_project_groups = mocker.spy(
        projects_service._groups_service,  # noqa: SLF001
        "list_project_groups_by_project_without_checking_permissions",
    )

    # inputs
    _patch_inputs = {
        "inputs": {
            "input_1": {
                "nodeUuid": sibling_node_id,
                "output": "out_1",
            },
        }
    }
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(_patch_inputs),
    )
    await assert_status(resp, expected)
    notify_project_nodes_update.assert_awaited_once()
    list_project_groups.assert_awaited_once()
    assert notify_project_nodes_update.await_args is not None
    # REST-triggered notifications are not strict (only the outbox consumer is)
    assert not notify_project_nodes_update.await_args.kwargs.get("strict", False)
    assert not DeepDiff(
        [f"{node_id}" for node_id in notify_project_nodes_update.await_args.args[2]],
        list(user_project["workbench"].keys()),
        ignore_order=True,
    )


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_204_NO_CONTENT)])
async def test_patch_project_node_inputs_with_data_type_change(
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
):
    node_id = next(iter(user_project["workbench"]))
    sibling_node_id = next(candidate for candidate in user_project["workbench"] if candidate != node_id)
    assert client.app
    base_url = client.app.router["patch_project_node"].url_for(project_id=user_project["uuid"], node_id=node_id)
    # inputs
    _patch_inputs = {
        "inputs": {
            "input_3": 0.0,  # <-- Changing type
            "input_2": 3.0,
            "input_1": {  # <-- Changing type
                "nodeUuid": sibling_node_id,
                "output": "out_1",
            },
        }
    }
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(_patch_inputs),
    )
    await assert_status(resp, expected)
    assert _patch_inputs["inputs"] == _patch_inputs["inputs"]

    # Change input data type
    _patch_inputs = {
        "inputs": {
            "input_3": {  # <-- Changing type
                "nodeUuid": sibling_node_id,
                "output": "out_1",
            },
            "input_2": 3.0,
            "input_1": 5.5,  # <-- Changing type
        }
    }
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(_patch_inputs),
    )
    await assert_status(resp, expected)
    assert _patch_inputs["inputs"] == _patch_inputs["inputs"]


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_204_NO_CONTENT)])
async def test_patch_project_node_service_key_with_error(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mocker: MockerFixture,
):
    node_id = next(iter(user_project["workbench"]))
    assert client.app
    url = client.app.router["patch_project_node"].url_for(project_id=user_project["uuid"], node_id=node_id)
    _patch_version = {"version": "2.0.9"}

    with mocker.patch(
        "simcore_service_webserver.projects._projects_service.catalog_rpc.check_for_service",
        side_effect=CatalogForbiddenRpcError(name="test"),
    ):
        resp = await client.patch(f"{url}", json=_patch_version)
        assert resp.status == status.HTTP_403_FORBIDDEN

    with mocker.patch(
        "simcore_service_webserver.projects._projects_service.catalog_rpc.check_for_service",
        side_effect=CatalogItemNotFoundRpcError(name="test"),
    ):
        resp = await client.patch(f"{url}", json=_patch_version)
        assert resp.status == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_204_NO_CONTENT)])
async def test_patch_project_node_does_not_deadlock_with_a_concurrent_parent_row_writer(
    mock_dynamic_scheduler: None,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    mock_catalog_rpc_check_for_service: None,
    mocked_notify_project_node_update,
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    asyncpg_engine: AsyncEngine,
):
    """a real PATCH must queue behind the parent project row instead of deadlocking with it"""
    project_uuid = user_project["uuid"]
    node_id = next(iter(user_project["workbench"]))
    assert client.app
    url = client.app.router["patch_project_node"].url_for(project_id=project_uuid, node_id=node_id)

    async def _patch_node() -> None:
        resp = await client.patch(f"{url}", json={"label": "concurrent-rename"})
        assert resp.status == expected, f"PATCH returned {resp.status}"

    # what a graph mutation does: lock the parent project row first, then write the node rows
    async with asyncpg_engine.connect() as conn, conn.begin():
        await projects_repository._lock_project_graph(conn, project_uuid=project_uuid)  # noqa: SLF001
        holder = await get_backend_pid(conn)

        # the PATCH starts only while the lock is held: it cannot complete before its first
        # statement queues on the parent row, so the interleaving below is always exercised
        patch_task = asyncio.create_task(_patch_node())

        async def _patch_is_done_or_behind_me() -> bool:
            # done() cannot mean "won the race": the PATCH started only after the lock above was
            # taken, so finishing now could only come from an unrelated early failure, which the
            # awaited patch_task below surfaces as the real error
            if patch_task.done():
                return True
            return await count_lock_waiters_behind(asyncpg_engine, holder) > 0

        await wait_until(_patch_is_done_or_behind_me, "the PATCH neither failed nor queued behind the parent lock")

        # the node row, written through the production repository only after the parent
        # row was locked first, in the same transaction
        await projects_nodes_repository.update(
            client.app,
            conn,
            project_id=project_uuid,
            node_id=node_id,
            partial_node=PartialNode.model_construct(progress=42.0),
        )

    # a deadlock surfaces as a failed PATCH (its backend was aborted), not as a stuck test
    await asyncio.wait_for(patch_task, timeout=TIMEOUT_S)

    final_node = await projects_nodes_repository.get(client.app, project_id=project_uuid, node_id=node_id)
    # both writers got their write in
    assert final_node.label == "concurrent-rename"
    assert final_node.progress == pytest.approx(42.0)
