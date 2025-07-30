# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-statements


import json
import uuid
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict

API_PREFIX = "/" + api_version_prefix


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
async def test_patch_project_entrypoint_access(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
):
    assert client.app
    base_url = client.app.router["patch_project"].url_for(
        project_id=user_project["uuid"]
    )
    # name & description
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(
            {
                "name": "testing-name",
            }
        ),
    )
    await assert_status(resp, expected)


@pytest.mark.parametrize(
    "user_role,expected", [(UserRole.USER, status.HTTP_204_NO_CONTENT)]
)
async def test_patch_project(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
):
    assert client.app
    base_url = client.app.router["patch_project"].url_for(
        project_id=user_project["uuid"]
    )
    # name & description
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(
            {
                "name": "testing-name",
                "description": "testing-description",
                "something": "non-existing",
            }
        ),
    )
    await assert_status(resp, expected)
    # thumbnail
    _patch_thumbnail = {"thumbnail": "https://raw.githubusercontent.com/test.png"}
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(_patch_thumbnail),
    )
    await assert_status(resp, expected)
    # UI
    _patch_ui = {
        "ui": {
            "workbench": {
                "77a04d71-b7e1-41d0-ab47-c99aa72b62d7": {
                    "position": {"x": 250, "y": 100}
                }
            }
        }
    }
    resp = await client.patch(f"{base_url}", data=json.dumps(_patch_ui))
    await assert_status(resp, expected)
    # UI 2
    _patch_ui_2 = {
        "ui": {
            "mode": "workbench",
            "slideshow": {},
            "workbench": {
                "d03d2752-e970-42cd-9483-69440ab9e4b7": {
                    "position": {"x": 250, "y": 100}
                }
            },
            "currentNodeId": "d03d2752-e970-42cd-9483-69440ab9e4b7",
        }
    }
    resp = await client.patch(f"{base_url}", data=json.dumps(_patch_ui_2))
    await assert_status(resp, expected)
    # quality
    _patch_quality = {
        "quality": {
            "enabled": True,
            "tsr_target": {
                "r01": {"level": 4, "references": ""},
                "r02": {"level": 4, "references": ""},
                "r03": {"level": 4, "references": ""},
                "r04": {"level": 4, "references": ""},
                "r05": {"level": 4, "references": ""},
                "r06": {"level": 4, "references": ""},
                "r07": {"level": 4, "references": ""},
                "r08": {"level": 4, "references": ""},
                "r09": {"level": 4, "references": ""},
                "r10": {"level": 4, "references": ""},
                "r03b": {"references": ""},
                "r03c": {"references": ""},
                "r07b": {"references": ""},
                "r07c": {"references": ""},
                "r07d": {"references": ""},
                "r07e": {"references": ""},
                "r08b": {"references": ""},
                "r10b": {"references": ""},
            },
            "tsr_current": {
                "r01": {"level": 0, "references": ""},
                "r02": {"level": 0, "references": ""},
                "r03": {"level": 0, "references": ""},
                "r04": {"level": 0, "references": ""},
                "r05": {"level": 0, "references": ""},
                "r06": {"level": 0, "references": ""},
                "r07": {"level": 0, "references": ""},
                "r08": {"level": 0, "references": ""},
                "r09": {"level": 0, "references": ""},
                "r10": {"level": 0, "references": ""},
                "r03b": {"references": ""},
                "r03c": {"references": ""},
                "r07b": {"references": ""},
                "r07c": {"references": ""},
                "r07d": {"references": ""},
                "r07e": {"references": ""},
                "r08b": {"references": ""},
                "r10b": {"references": ""},
            },
        }
    }
    resp = await client.patch(f"{base_url}", data=json.dumps(_patch_quality))
    await assert_status(resp, expected)
    # classifiers
    _patch_classifiers = {"classifiers": ["RRID:SCR_012345", "RRID:SCR_054321"]}
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(_patch_classifiers),
    )
    await assert_status(resp, expected)
    # dev
    _patch_dev = {"dev": {"random": "random"}}
    resp = await client.patch(f"{base_url}", data=json.dumps(_patch_dev))
    await assert_status(resp, expected)

    # Get project
    get_url = client.app.router["get_project"].url_for(project_id=user_project["uuid"])
    resp = await client.get(f"{get_url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["uuid"] == user_project["uuid"]
    assert data["name"] == "testing-name"
    assert data["description"] == "testing-description"
    assert data["thumbnail"] == _patch_thumbnail["thumbnail"]
    assert data["classifiers"] == _patch_classifiers["classifiers"]
    assert data["ui"] == _patch_ui_2["ui"]
    assert data["quality"] == _patch_quality["quality"]
    assert data["dev"] == _patch_dev["dev"]


@pytest.mark.parametrize(
    "user_role,expected", [(UserRole.USER, status.HTTP_204_NO_CONTENT)]
)
async def test_patch_project_with_client_session_header(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
):
    assert client.app
    base_url = client.app.router["patch_project"].url_for(
        project_id=user_project["uuid"]
    )

    # Generate a valid UUID for client session ID
    client_session_id = str(uuid.uuid4())

    # Test patch with X-Client-Session-Id header - should succeed
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(
            {
                "name": "testing-name-with-session",
                "description": "testing-description-with-session",
            }
        ),
        headers={"X-Client-Session-Id": client_session_id},
    )
    await assert_status(resp, expected)

    # Test patch without X-Client-Session-Id header - should also succeed (header is optional)
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(
            {
                "name": "testing-name-without-session",
                "description": "testing-description-without-session",
            }
        ),
    )
    await assert_status(resp, expected)

    # Test patch with invalid X-Client-Session-Id header - should fail with validation error
    resp = await client.patch(
        f"{base_url}",
        data=json.dumps(
            {
                "name": "testing-name-invalid-session",
                "description": "testing-description-invalid-session",
            }
        ),
        headers={"X-Client-Session-Id": "invalid-uuid-format"},
    )
    # This should fail validation since it's not a proper UUID
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)
