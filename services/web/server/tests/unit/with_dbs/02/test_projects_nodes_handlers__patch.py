# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-statements


import json
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from deepdiff import DeepDiff
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from servicelib.rabbitmq.rpc_interfaces.catalog.errors import (
    CatalogForbiddenError,
    CatalogItemNotFoundError,
)
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict

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
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
):
    node_id = next(iter(user_project["workbench"]))
    assert client.app
    base_url = client.app.router["patch_project_node"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps({"label": "testing-string"}),
    )
    await assert_status(resp, expected)


@pytest.mark.parametrize(
    "user_role,expected", [(UserRole.USER, status.HTTP_204_NO_CONTENT)]
)
async def test_patch_project_node(
    mock_dynamic_scheduler: None,
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mock_catalog_rpc_check_for_service: None,
):
    node_id = next(iter(user_project["workbench"]))
    assert client.app
    base_url = client.app.router["patch_project_node"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(
            {"label": "testing-string", "progress": None, "something": "non-existing"}
        ),
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
            "9502ce16-1fe9-5b9a-86fa-9a9ba186174b",
            "c374e5ba-fc42-5c40-ae74-df7ef337f597",
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
                "eTag": "d41d8cd98f00b204e9800998ecf8427e",
            }
        }
    }
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(_patch_outputs),
    )
    await assert_status(resp, expected)

    # Get project
    get_url = client.app.router["get_project"].url_for(project_id=user_project["uuid"])
    resp = await client.get(f"{get_url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    _tested_node = data["workbench"][node_id]

    assert _tested_node["label"] == "testing-string"
    assert _tested_node["progress"] is None
    assert _tested_node["key"] == _patch_key["key"]
    assert _tested_node["version"] == _patch_version["version"]
    assert _tested_node["inputs"] == _patch_inputs["inputs"]
    assert _tested_node["inputsRequired"] == _patch_inputs_required["inputsRequired"]
    assert _tested_node["inputNodes"] == _patch_input_nodes["inputNodes"]
    assert _tested_node["bootOptions"] == _patch_boot_options["bootOptions"]
    assert _tested_node["outputs"] == _patch_outputs["outputs"]


@pytest.mark.parametrize(
    "user_role,expected", [(UserRole.USER, status.HTTP_204_NO_CONTENT)]
)
async def test_patch_project_node_notifies(
    mocker: MockerFixture,
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mock_catalog_rpc_check_for_service,
    mocked_notify_project_node_update,
):

    node_id = next(iter(user_project["workbench"]))
    assert client.app
    base_url = client.app.router["patch_project_node"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )

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


@pytest.mark.parametrize(
    "user_role,expected", [(UserRole.USER, status.HTTP_204_NO_CONTENT)]
)
async def test_patch_project_node_inputs_notifies(
    mocker: MockerFixture,
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mocked_notify_project_node_update,
):
    node_id = next(iter(user_project["workbench"]))
    assert client.app
    base_url = client.app.router["patch_project_node"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )

    # inputs
    _patch_inputs = {
        "inputs": {
            "input_1": {
                "nodeUuid": "c374e5ba-fc42-5c40-ae74-df7ef337f597",
                "output": "out_1",
            },
        }
    }
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(_patch_inputs),
    )
    await assert_status(resp, expected)
    assert mocked_notify_project_node_update.call_count > 1
    # 1 message per node updated
    assert not DeepDiff(
        [
            call_args[0][2]
            for call_args in mocked_notify_project_node_update.await_args_list
        ],
        list(user_project["workbench"].keys()),
        ignore_order=True,
    )


@pytest.mark.parametrize(
    "user_role,expected", [(UserRole.USER, status.HTTP_204_NO_CONTENT)]
)
async def test_patch_project_node_inputs_with_data_type_change(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
):
    node_id = next(iter(user_project["workbench"]))
    assert client.app
    base_url = client.app.router["patch_project_node"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    # inputs
    _patch_inputs = {
        "inputs": {
            "input_3": 0.0,  # <-- Changing type
            "input_2": 3.0,
            "input_1": {  # <-- Changing type
                "nodeUuid": "c374e5ba-fc42-5c40-ae74-df7ef337f597",
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
                "nodeUuid": "c374e5ba-fc42-5c40-ae74-df7ef337f597",
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


@pytest.mark.parametrize(
    "user_role,expected", [(UserRole.USER, status.HTTP_204_NO_CONTENT)]
)
async def test_patch_project_node_service_key_with_error(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mocker: MockerFixture,
):
    node_id = next(iter(user_project["workbench"]))
    assert client.app
    url = client.app.router["patch_project_node"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    _patch_version = {"version": "2.0.9"}

    with mocker.patch(
        "simcore_service_webserver.projects._projects_service.catalog_rpc.check_for_service",
        side_effect=CatalogForbiddenError(name="test"),
    ):
        resp = await client.patch(f"{url}", json=_patch_version)
        assert resp.status == status.HTTP_403_FORBIDDEN

    with mocker.patch(
        "simcore_service_webserver.projects._projects_service.catalog_rpc.check_for_service",
        side_effect=CatalogItemNotFoundError(name="test"),
    ):
        resp = await client.patch(f"{url}", json=_patch_version)
        assert resp.status == status.HTTP_404_NOT_FOUND
