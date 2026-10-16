# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-statements


import asyncio
import json
from http import HTTPStatus
from typing import Final
from unittest import mock

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from deepdiff import DeepDiff
from models_library.projects_nodes import PartialNode
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
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


#
# Deadlock regression (https://github.com/ITISFoundation/private-issues/issues/669)
#
# On 2026-10-16 production raised DeadlockDetectedError on this very entrypoint: the PATCH
# wrote the node row and the `projects_nodes_changed` trigger then locked the parent
# `projects` row, while a graph mutation had locked the parent row first and was going for
# the node rows. This test runs the real endpoint against that interleaving; the repo-level
# twin is packages/postgres-database/tests/test_utils_projects_nodes.py
# ::test_node_writes_do_not_deadlock_with_a_concurrent_parent_row_writer
#

# test instrumentation only: which backend holds/waits on which lock
_WAITERS_BEHIND_SQL: Final[str] = (
    "SELECT count(*) FROM pg_stat_activity "
    "WHERE wait_event_type = 'Lock' AND pid <> pg_backend_pid() AND :pid = ANY(pg_blocking_pids(pid))"
)
_TIMEOUT_S: Final[float] = 30.0


async def _wait_until(condition, what: str) -> None:
    async def _poll() -> None:
        while not await condition():  # noqa: ASYNC110  # polls the state of the database, no event to wait for
            await asyncio.sleep(0.05)

    try:
        await asyncio.wait_for(_poll(), timeout=_TIMEOUT_S)
    except TimeoutError:
        pytest.fail(what)


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

    patch_task: asyncio.Task[None] = asyncio.create_task(_patch_node())

    # what a graph mutation does: lock the parent project row first, then write the node rows
    async with asyncpg_engine.connect() as conn, conn.begin():
        await conn.execute(
            sa.text("SELECT uuid FROM projects WHERE uuid = :project_uuid FOR NO KEY UPDATE"),
            {"project_uuid": project_uuid},
        )
        holder = int(await conn.scalar(sa.text("SELECT pg_backend_pid()")))

        async def _patch_is_done_or_behind_me() -> bool:
            if patch_task.done():
                return True
            async with asyncpg_engine.connect() as probe:
                return bool(await probe.scalar(sa.text(_WAITERS_BEHIND_SQL), {"pid": holder}))

        await _wait_until(_patch_is_done_or_behind_me, "the PATCH neither finished nor queued behind the parent lock")

        # the node row, written only after the parent row was locked first
        await conn.execute(
            sa.text("UPDATE projects_nodes SET progress = 42.0 WHERE project_uuid = :pid AND node_id = :nid"),
            {"pid": project_uuid, "nid": node_id},
        )

    # a deadlock surfaces as a failed PATCH (its backend was aborted), not as a stuck test
    await asyncio.wait_for(patch_task, timeout=_TIMEOUT_S)

    async with asyncpg_engine.connect() as conn:
        label, progress = (
            await conn.execute(
                sa.text("SELECT label, progress FROM projects_nodes WHERE project_uuid = :pid AND node_id = :nid"),
                {"pid": project_uuid, "nid": node_id},
            )
        ).one()
    # both writers got their write in
    assert label == "concurrent-rename"
    assert progress == 42.0
