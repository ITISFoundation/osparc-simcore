# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-statements


import pytest
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser, UserInfoDict
from simcore_postgres_database.models.projects import projects
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict

API_PREFIX = "/" + api_version_prefix


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_project_comments_user_role_access(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    user_role: UserRole,
    expected: type[web.HTTPException],
):
    base_url = client.app.router["list_project_comments"].url_for(
        project_uuid=user_project["uuid"]
    )
    resp = await client.get(base_url)
    assert resp.status == 401 if user_role == UserRole.ANONYMOUS else 200


@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/osparc-issues/issues/993"
)
@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.USER, web.HTTPOk),
    ],
)
async def test_project_comments_full_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: type[web.HTTPException],
    postgres_db: sa.engine.Engine,
):
    base_url = client.app.router["list_project_comments"].url_for(
        project_uuid=user_project["uuid"]
    )
    resp = await client.get(base_url)
    data, _, meta, links = await assert_status(
        resp,
        expected,
        include_meta=True,
        include_links=True,
    )
    assert data == []
    assert meta["total"] == 0
    assert links

    # Now we will add first comment
    body = {"contents": "My first comment"}
    resp = await client.post(base_url, json=body)
    data, _ = await assert_status(
        resp,
        web.HTTPCreated,
    )
    first_comment_id = data["comment_id"]

    # Now we will add second comment
    resp = await client.post(base_url, json={"contents": "My second comment"})
    data, _ = await assert_status(
        resp,
        web.HTTPCreated,
    )
    second_comment_id = data["comment_id"]

    # Now we will list all comments for the project
    resp = await client.get(base_url)
    data, _, meta, links = await assert_status(
        resp,
        expected,
        include_meta=True,
        include_links=True,
    )
    assert len(data) == 2
    assert meta["total"] == 2
    assert links

    # Now we will update the second comment
    updated_comment = "Updated second comment"
    resp = await client.put(
        base_url / f"{second_comment_id}",
        json={"contents": updated_comment},
    )
    data, _ = await assert_status(
        resp,
        expected,
    )

    # Now we will get the second comment
    resp = await client.get(base_url / f"{second_comment_id}")
    data, _ = await assert_status(
        resp,
        expected,
    )
    assert data["contents"] == updated_comment

    # Now we will delete the second comment
    resp = await client.delete(base_url / f"{second_comment_id}")
    data, _ = await assert_status(
        resp,
        web.HTTPNoContent,
    )

    # Now we will list all comments for the project
    resp = await client.get(base_url)
    data, _, meta, links = await assert_status(
        resp,
        expected,
        include_meta=True,
        include_links=True,
    )
    assert meta["total"] == 1
    assert links
    assert len(data) == 1

    # Now we will log as a different user
    async with LoggedUser(client) as new_logged_user:
        # As this user does not have access to the project, they should get 404
        resp = await client.get(base_url)
        _, errors = await assert_status(
            resp,
            web.HTTPNotFound,
        )
        assert errors

        resp = await client.get(base_url / f"{first_comment_id}")
        _, errors = await assert_status(
            resp,
            web.HTTPNotFound,
        )
        assert errors

        # Now we will share the project with the new user
        with postgres_db.connect() as con:
            result = con.execute(
                projects.update()
                .values(
                    **{
                        "access_rights": {
                            str(logged_user["primary_gid"]): {
                                "read": True,
                                "write": True,
                                "delete": True,
                            },
                            str(new_logged_user["primary_gid"]): {
                                "read": True,
                                "write": True,
                                "delete": True,
                            },
                        }
                    }
                )
                .where(projects.c.uuid == user_project["uuid"])
            )

        # Now the user should have access to the project now
        # New user will add comment
        resp = await client.post(
            base_url,
            json={"contents": "My first comment as a new user"},
        )
        data, _ = await assert_status(
            resp,
            web.HTTPCreated,
        )
        new_user_comment_id = data["comment_id"]

        # New user will modify the comment
        updated_comment = "Updated My first comment as a new user"
        resp = await client.put(
            base_url / f"{new_user_comment_id}",
            json={"contents": updated_comment},
        )
        data, _ = await assert_status(
            resp,
            expected,
        )
        assert data["contents"] == updated_comment

        # New user will list all comments
        resp = await client.get(base_url)
        data, _, meta, links = await assert_status(
            resp,
            expected,
            include_meta=True,
            include_links=True,
        )
        assert meta["total"] == 2
        assert links
        assert len(data) == 2

        # New user will modify comment of the previous user
        updated_comment = "Updated comment of previous user"
        resp = await client.put(
            base_url / f"{first_comment_id}",
            json={"contents": updated_comment},
        )
        data, _ = await assert_status(
            resp,
            expected,
        )
        assert data["contents"] == updated_comment

        # New user will delete comment of the previous user
        resp = await client.delete(base_url / f"{first_comment_id}")
        data, _ = await assert_status(
            resp,
            web.HTTPNoContent,
        )
