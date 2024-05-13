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
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict

API_PREFIX = "/" + api_version_prefix


@pytest.fixture
def mock_catalog_api_get_services_for_user_in_product(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_webserver.projects._crud_handlers.get_services_for_user_in_product",
        spec=True,
        return_value=[],
    )


@pytest.fixture
def mock_project_uses_available_services(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_webserver.projects._crud_handlers.project_uses_available_services",
        spec=True,
        return_value=True,
    )


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_204_NO_CONTENT),
        (UserRole.TESTER, status.HTTP_204_NO_CONTENT),
        (UserRole.ADMIN, status.HTTP_204_NO_CONTENT),
        (UserRole.PRODUCT_OWNER, status.HTTP_204_NO_CONTENT),
    ],
)
async def test_patch_project_node_entrypoint_access(
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
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mock_catalog_api_get_services_for_user_in_product,
    mock_project_uses_available_services,
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

    # Get project
    get_url = client.app.router["get_project"].url_for(project_id=user_project["uuid"])
    resp = await client.get(f"{get_url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    _tested_node = data["workbench"][node_id]

    assert _tested_node["label"] == "testing-string"
    assert _tested_node["progress"] == None
    assert _tested_node["version"] == _patch_version["version"]
    assert _tested_node["inputs"] == _patch_inputs["inputs"]
    assert _tested_node["inputNodes"] == _patch_input_nodes["inputNodes"]
    assert _tested_node["bootOptions"] == _patch_boot_options["bootOptions"]
