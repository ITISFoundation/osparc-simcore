# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# type: ignore

from copy import deepcopy
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.api_schemas_catalog import ServiceAccessRightsGet
from models_library.projects_nodes import Node, NodeID
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict
from yarl import URL


@pytest.fixture
def workbench_db_column() -> dict[str, Any]:
    return {
        "13220a1d-a569-49de-b375-904301af9295": {
            "key": "simcore/services/comp/itis/sleeper",
            "version": "2.1.4",
            "label": "sleeper",
        },
        "38a0d401-af4b-4ea7-ab4c-5005c712a546": {
            "key": "simcore/services/frontend/parameter/integer",
            "version": "1.0.0",
            "label": "integer",
        },
        "08d15a6c-ae7b-4ea1-938e-4ce81a360ffa": {
            "key": "simcore/services/comp/itis/sleeper",
            "version": "2.1.5",
            "label": "sleeper_2",
        },
    }


@pytest.fixture
def workbench(workbench_db_column: dict[str, Any]) -> dict[NodeID, Node]:
    # convert to  model
    return parse_obj_as(dict[NodeID, Node], workbench_db_column)


@pytest.fixture
def fake_project(
    fake_project: ProjectDict, workbench_db_column: dict[str, Any]
) -> ProjectDict:
    # OVERRIDES user_project
    project = deepcopy(fake_project)
    project["workbench"] = workbench_db_column
    return project


@pytest.fixture
def mock_catalog_api_get_service_access_rights_response(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_webserver.projects._nodes_handlers.catalog_client.get_service_access_rights",
        spec=True,
        side_effect=[
            ServiceAccessRightsGet(
                service_key="simcore/services/comp/itis/sleeper",
                service_version="2.1.4",
                gids_with_access_rights={
                    1: {"execute_access": True},
                    5: {"execute_access": True},
                },
            ),
            ServiceAccessRightsGet(
                service_key="simcore/services/frontend/parameter/integer",
                service_version="1.0.0",
                gids_with_access_rights={1: {"execute_access": True}},
            ),
            ServiceAccessRightsGet(
                service_key="simcore/services/comp/itis/sleeper",
                service_version="2.1.5",
                gids_with_access_rights={
                    4: {"execute_access": True},
                    1: {"execute_access": True},
                },
            ),
        ],
    )


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_user_role_access(
    client: TestClient,
    user_project: ProjectDict,
    expected: type[web.HTTPException],
    mock_catalog_api_get_service_access_rights_response,
):
    assert client.app

    project_id = user_project["uuid"]
    for_gid = 3

    expected_url = client.app.router["get_project_services_access_for_gid"].url_for(
        project_id=project_id
    )
    assert URL(f"/v0/projects/{project_id}/nodes/-/services:access") == expected_url

    resp = await client.get(
        f"/v0/projects/{project_id}/nodes/-/services:access?for_gid={for_gid}"
    )
    project_access, error = await assert_status(resp, expected_cls=expected)

    if not error:
        assert project_access == {"gid": for_gid, "accessible": True}


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_accessible_thanks_to_everyone_group_id(
    client: TestClient, user_project: ProjectDict, mocker: MockerFixture
):
    mocker.patch(
        "simcore_service_webserver.projects._nodes_handlers.catalog_client.get_service_access_rights",
        spec=True,
        side_effect=[
            ServiceAccessRightsGet(
                service_key="simcore/services/comp/itis/sleeper",
                service_version="2.1.4",
                gids_with_access_rights={1: {"execute_access": True}},
            ),
            ServiceAccessRightsGet(
                service_key="simcore/services/frontend/parameter/integer",
                service_version="1.0.0",
                gids_with_access_rights={
                    1: {"execute_access": True},
                    2: {"execute_access": True},
                },
            ),
            ServiceAccessRightsGet(
                service_key="simcore/services/comp/itis/sleeper",
                service_version="2.1.5",
                gids_with_access_rights={
                    1: {"execute_access": True},
                    3: {"execute_access": True},
                },
            ),
        ],
    )

    assert client.app

    project_id = user_project["uuid"]
    for_gid = 3

    expected_url = client.app.router["get_project_services_access_for_gid"].url_for(
        project_id=project_id
    )
    assert URL(f"/v0/projects/{project_id}/nodes/-/services:access") == expected_url

    resp = await client.get(
        f"/v0/projects/{project_id}/nodes/-/services:access?for_gid={for_gid}"
    )
    data, _ = await assert_status(resp, web.HTTPOk)

    assert data == {"gid": for_gid, "accessible": True}


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_accessible_thanks_to_concrete_group_id(
    client: TestClient, user_project: ProjectDict, mocker: MockerFixture
):
    mocker.patch(
        "simcore_service_webserver.projects._nodes_handlers.catalog_client.get_service_access_rights",
        spec=True,
        side_effect=[
            ServiceAccessRightsGet(
                service_key="simcore/services/comp/itis/sleeper",
                service_version="2.1.4",
                gids_with_access_rights={
                    3: {"execute_access": True},
                    5: {"execute_access": True},
                },
            ),
            ServiceAccessRightsGet(
                service_key="simcore/services/frontend/parameter/integer",
                service_version="1.0.0",
                gids_with_access_rights={
                    1: {"execute_access": True}
                },  # <-- GROUP ID FOR EVERYONE
            ),
            ServiceAccessRightsGet(
                service_key="simcore/services/comp/itis/sleeper",
                service_version="2.1.5",
                gids_with_access_rights={3: {"execute_access": True}},
            ),
        ],
    )

    assert client.app

    project_id = user_project["uuid"]
    for_gid = 3

    expected_url = client.app.router["get_project_services_access_for_gid"].url_for(
        project_id=project_id
    )
    assert URL(f"/v0/projects/{project_id}/nodes/-/services:access") == expected_url

    resp = await client.get(
        f"/v0/projects/{project_id}/nodes/-/services:access?for_gid={for_gid}"
    )
    data, _ = await assert_status(resp, web.HTTPOk)

    assert data == {"gid": for_gid, "accessible": True}


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_not_accessible_for_one_service(
    client: TestClient, user_project: ProjectDict, mocker: MockerFixture
):
    mocker.patch(
        "simcore_service_webserver.projects._nodes_handlers.catalog_client.get_service_access_rights",
        spec=True,
        side_effect=[
            ServiceAccessRightsGet(
                service_key="simcore/services/comp/itis/sleeper",
                service_version="2.1.4",
                gids_with_access_rights={
                    2: {"execute_access": True},
                    4: {"execute_access": True},
                },
            ),
            ServiceAccessRightsGet(
                service_key="simcore/services/frontend/parameter/integer",
                service_version="1.0.0",
                gids_with_access_rights={
                    3: {"execute_access": True},
                    2: {"execute_access": True},
                },
            ),
            ServiceAccessRightsGet(
                service_key="simcore/services/comp/itis/sleeper",
                service_version="2.1.5",
                gids_with_access_rights={3: {"execute_access": True}},
            ),
        ],
    )

    assert client.app

    project_id = user_project["uuid"]
    for_gid = 3

    expected_url = client.app.router["get_project_services_access_for_gid"].url_for(
        project_id=project_id
    )
    assert URL(f"/v0/projects/{project_id}/nodes/-/services:access") == expected_url

    resp = await client.get(
        f"/v0/projects/{project_id}/nodes/-/services:access?for_gid={for_gid}"
    )
    data, _ = await assert_status(resp, web.HTTPOk)

    assert data == {
        "gid": for_gid,
        "accessible": False,
        "inaccessible_services": [
            {"key": "simcore/services/comp/itis/sleeper", "version": "2.1.4"}
        ],
    }


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_not_accessible_for_more_services(
    client: TestClient, user_project: ProjectDict, mocker: MockerFixture
):
    mocker.patch(
        "simcore_service_webserver.projects._nodes_handlers.catalog_client.get_service_access_rights",
        spec=True,
        side_effect=[
            ServiceAccessRightsGet(
                service_key="simcore/services/comp/itis/sleeper",
                service_version="2.1.4",
                gids_with_access_rights={
                    2: {"execute_access": True},
                    5: {"execute_access": True},
                },
            ),
            ServiceAccessRightsGet(
                service_key="simcore/services/frontend/parameter/integer",
                service_version="1.0.0",
                gids_with_access_rights={
                    4: {"execute_access": True},
                    5: {"execute_access": True},
                },
            ),
            ServiceAccessRightsGet(
                service_key="simcore/services/comp/itis/sleeper",
                service_version="2.1.5",
                gids_with_access_rights={
                    4: {"execute_access": True},
                    5: {"execute_access": True},
                },
            ),
        ],
    )

    assert client.app

    project_id = user_project["uuid"]
    for_gid = 3

    expected_url = client.app.router["get_project_services_access_for_gid"].url_for(
        project_id=project_id
    )
    assert URL(f"/v0/projects/{project_id}/nodes/-/services:access") == expected_url

    resp = await client.get(
        f"/v0/projects/{project_id}/nodes/-/services:access?for_gid={for_gid}"
    )
    data, _ = await assert_status(resp, web.HTTPOk)

    assert data == {
        "gid": for_gid,
        "accessible": False,
        "inaccessible_services": [
            {"key": "simcore/services/comp/itis/sleeper", "version": "2.1.4"},
            {"key": "simcore/services/frontend/parameter/integer", "version": "1.0.0"},
            {"key": "simcore/services/comp/itis/sleeper", "version": "2.1.5"},
        ],
    }


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_not_accessible_for_service_because_of_execute_access_false(
    client: TestClient, user_project: ProjectDict, mocker: MockerFixture
):
    mocker.patch(
        "simcore_service_webserver.projects._nodes_handlers.catalog_client.get_service_access_rights",
        spec=True,
        side_effect=[
            ServiceAccessRightsGet(
                service_key="simcore/services/comp/itis/sleeper",
                service_version="2.1.4",
                gids_with_access_rights={3: {"execute_access": False}},  # <-- FALSE
            ),
            ServiceAccessRightsGet(
                service_key="simcore/services/frontend/parameter/integer",
                service_version="1.0.0",
                gids_with_access_rights={3: {"execute_access": True}},
            ),
            ServiceAccessRightsGet(
                service_key="simcore/services/comp/itis/sleeper",
                service_version="2.1.5",
                gids_with_access_rights={3: {"execute_access": True}},
            ),
        ],
    )

    assert client.app

    project_id = user_project["uuid"]
    for_gid = 3

    expected_url = client.app.router["get_project_services_access_for_gid"].url_for(
        project_id=project_id
    )
    assert URL(f"/v0/projects/{project_id}/nodes/-/services:access") == expected_url

    resp = await client.get(
        f"/v0/projects/{project_id}/nodes/-/services:access?for_gid={for_gid}"
    )
    data, _ = await assert_status(resp, web.HTTPOk)

    assert data == {
        "gid": for_gid,
        "accessible": False,
        "inaccessible_services": [
            {"key": "simcore/services/comp/itis/sleeper", "version": "2.1.4"}
        ],
    }
