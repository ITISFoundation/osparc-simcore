# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.basic_types import IdInt
from models_library.groups import EVERYONE_GROUP_ID
from models_library.products import ProductName
from models_library.projects_state import (
    ProjectLocked,
    ProjectRunningState,
    ProjectState,
    ProjectStatus,
    RunningState,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.postgres_tags import create_tag, delete_tag
from pytest_simcore.helpers.webserver_login import NewUser, UserInfoDict
from pytest_simcore.helpers.webserver_projects import assert_get_same_project
from servicelib.aiohttp import status
from simcore_postgres_database.models.tags import tags
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.db.plugin import get_database_engine
from simcore_service_webserver.products._service import get_product
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def _clean_tags_table(postgres_db: sa.engine.Engine) -> Iterator[None]:
    yield
    with postgres_db.connect() as conn:
        conn.execute(tags.delete())


@pytest.fixture
def user_role() -> UserRole:
    # All tests in test_tags assume USER's role
    # i.e. Used in `logged_user` and `user_project` fixtures
    return UserRole.USER


async def test_tags_to_studies(
    client: TestClient,
    faker: Faker,
    user_project: ProjectDict,
):
    assert client.app

    # Add test tags
    added_tags = []

    for tag in [
        {"name": "tag1", "description": faker.sentence(), "color": "#f00"},
        {"name": "tag2", "description": faker.sentence(), "color": "#00f"},
    ]:
        url = client.app.router["create_tag"].url_for()
        resp = await client.post(f"{url}", json=tag)
        added_tag, _ = await assert_status(resp, status.HTTP_201_CREATED)
        added_tags.append(added_tag)

        # Add tag to study
        url = client.app.router["add_project_tag"].url_for(
            project_uuid=user_project.get("uuid"), tag_id=str(added_tag.get("id"))
        )
        resp = await client.post(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)

        # Tag is included in response
        assert added_tag["id"] in data["tags"]

    # check the tags are in
    user_project["tags"] = [tag["id"] for tag in added_tags]
    user_project["state"] = jsonable_encoder(
        ProjectState(
            locked=ProjectLocked(value=False, status=ProjectStatus.CLOSED),
            state=ProjectRunningState(value=RunningState.UNKNOWN),
        ),
        exclude_unset=True,
    )
    user_project["folderId"] = None

    data = await assert_get_same_project(client, user_project, status.HTTP_200_OK)

    # Delete tag0
    url = client.app.router["delete_tag"].url_for(tag_id=str(added_tags[0].get("id")))
    resp = await client.delete(f"{url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # Get project and check that tag is no longer there
    user_project["tags"].remove(added_tags[0]["id"])
    data = await assert_get_same_project(client, user_project, status.HTTP_200_OK)
    assert added_tags[0].get("id") not in data.get("tags")

    # Remove tag1 from project
    url = client.app.router["remove_project_tag"].url_for(
        project_uuid=user_project.get("uuid"), tag_id=str(added_tags[1].get("id"))
    )
    resp = await client.post(f"{url}")
    await assert_status(resp, status.HTTP_200_OK)

    # Get project and check that tag is no longer there
    user_project["tags"].remove(added_tags[1]["id"])
    data = await assert_get_same_project(client, user_project, status.HTTP_200_OK)
    assert added_tags[1].get("id") not in data.get("tags")

    # Delete tag1
    url = client.app.router["delete_tag"].url_for(tag_id=str(added_tags[1].get("id")))
    resp = await client.delete(f"{url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)


@pytest.fixture
async def everybody_tag_id(client: TestClient) -> AsyncIterator[int]:
    assert client.app
    engine = get_database_engine(client.app)
    assert engine

    async with engine.acquire() as conn:
        tag_id = await create_tag(
            conn,
            name="TG",
            description="tag for EVERYBODY",
            color="#f00",
            group_id=1,
            read=True,  # <--- READ ONLY
            write=False,
            delete=False,
        )

        yield tag_id

        await delete_tag(conn, tag_id=tag_id)


async def test_read_tags(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    everybody_tag_id: int,
):
    assert client.app
    assert UserRole(logged_user["role"]) == user_role

    url = client.app.router["list_tags"].url_for()
    resp = await client.get(f"{url}")
    datas, _ = await assert_status(resp, status.HTTP_200_OK)

    assert datas == [
        {
            "id": everybody_tag_id,
            "name": "TG",
            "description": "tag for EVERYBODY",
            "color": "#f00",
            "accessRights": {"read": True, "write": False, "delete": False},
        }
    ]


async def test_create_and_update_tags(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    everybody_tag_id: int,
    _clean_tags_table: None,
):
    assert client.app
    assert UserRole(logged_user["role"]) == user_role

    # (1) create tag
    url = client.app.router["create_tag"].url_for()
    resp = await client.post(
        f"{url}",
        json={"name": "T", "color": "#f00"},
    )
    created, _ = await assert_status(resp, status.HTTP_201_CREATED)

    assert created == {
        "id": created["id"],
        "name": "T",
        "description": None,
        "color": "#f00",
        "accessRights": {"read": True, "write": True, "delete": True},
    }

    # (2) update created tag
    url = client.app.router["update_tag"].url_for(tag_id=f"{created['id']}")
    resp = await client.patch(
        f"{url}",
        json={"description": "This is my tag"},
    )

    updated, _ = await assert_status(resp, status.HTTP_200_OK)
    created.update(description="This is my tag")
    assert updated == created

    # (3) Cannot update tag because it has not enough access rights
    url = client.app.router["update_tag"].url_for(tag_id=f"{everybody_tag_id}")
    resp = await client.patch(
        f"{url}",
        json={"description": "I have NO WRITE ACCESS TO THIS TAG"},
    )
    _, error = await assert_status(resp, status.HTTP_403_FORBIDDEN)
    assert error


async def test_create_tags_with_order_index(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    _clean_tags_table: None,
):
    assert client.app
    assert UserRole(logged_user["role"]) == user_role

    # (1) create tags but set the order in reverse order of creation
    url = client.app.router["create_tag"].url_for()
    num_tags = 3
    expected_tags: list[Any] = [None] * num_tags
    for creation_index, priority_index in enumerate(range(num_tags - 1, -1, -1)):
        resp = await client.post(
            f"{url}",
            json={
                "name": f"T{creation_index}-{priority_index}",
                "description": f"{creation_index=}, {priority_index=}",
                "color": "#f00",
                "priority": priority_index,
            },
        )
        created, _ = await assert_status(resp, status.HTTP_201_CREATED)
        expected_tags[priority_index] = created

    url = client.app.router["list_tags"].url_for()
    resp = await client.get(f"{url}")
    got, _ = await assert_status(resp, status.HTTP_200_OK)
    assert got == expected_tags

    # (2) lets update all priorities in reverse order
    for new_order_index, tag in enumerate(reversed(expected_tags)):
        url = client.app.router["update_tag"].url_for(tag_id=f"{tag['id']}")
        resp = await client.patch(
            f"{url}",
            json={"priority": new_order_index},
        )
        updated, _ = await assert_status(resp, status.HTTP_200_OK)
        # NOTE: priority is not included in TagGet for now
        assert updated == tag

    url = client.app.router["list_tags"].url_for()
    resp = await client.get(f"{url}")
    got, _ = await assert_status(resp, status.HTTP_200_OK)
    assert got == expected_tags[::-1]

    # (3) new tag without priority should get last (because is last created)
    url = client.app.router["create_tag"].url_for()
    resp = await client.post(
        f"{url}",
        json={"name": "New", "color": "#f00", "description": "w/o priority"},
    )
    last_created, _ = await assert_status(resp, status.HTTP_201_CREATED)

    url = client.app.router["list_tags"].url_for()
    resp = await client.get(f"{url}")
    got, _ = await assert_status(resp, status.HTTP_200_OK)
    assert got == [*expected_tags[::-1], last_created]


async def test_share_tags_by_creating_associated_groups(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    _clean_tags_table: None,
):
    assert client.app
    assert UserRole(logged_user["role"]) == user_role

    # CREATE
    url = client.app.router["create_tag"].url_for()
    resp = await client.post(
        f"{url}",
        json={"name": "shared", "color": "#fff"},
    )
    tag, _ = await assert_status(resp, status.HTTP_201_CREATED)

    # LIST
    url = client.app.router["list_tag_groups"].url_for(tag_id=f"{tag['id']}")
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    # check ownership
    assert len(data) == 1
    assert data[0]["gid"] == logged_user["primary_gid"]
    assert data[0]["read"] is True
    assert data[0]["write"] is True
    assert data[0]["delete"] is True

    async with NewUser(
        app=client.app,
    ) as new_user:
        # CREATE SHARE
        url = client.app.router["create_tag_group"].url_for(
            tag_id=f"{tag['id']}",
            group_id=f"{new_user['primary_gid']}",
        )
        resp = await client.post(
            f"{url}",
            json={"read": True, "write": False, "delete": False},
        )
        data, _ = await assert_status(resp, status.HTTP_201_CREATED)
        assert data["gid"] == new_user["primary_gid"]

        # check can read
        url = client.app.router["list_tag_groups"].url_for(tag_id=f"{tag['id']}")
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data) == 2
        assert data[1]["gid"] == new_user["primary_gid"]
        assert data[1]["read"] is True
        assert data[1]["write"] is False
        assert data[1]["delete"] is False

        # REPLACE SHARE
        url = client.app.router["replace_tag_group"].url_for(
            tag_id=f"{tag['id']}",
            group_id=f"{new_user['primary_gid']}",
        )
        resp = await client.put(
            f"{url}",
            json={"read": True, "write": True, "delete": False},
        )
        data, _ = await assert_status(resp, status.HTTP_200_OK)

        # test can perform new combinations
        assert data["gid"] == new_user["primary_gid"]

        url = client.app.router["list_tag_groups"].url_for(tag_id=f"{tag['id']}")
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data) == 2
        assert data[1]["gid"] == new_user["primary_gid"]
        assert data[1]["read"] is True
        assert data[1]["write"] is True
        assert data[1]["delete"] is False

        # DELETE SHARE
        url = client.app.router["delete_tag_group"].url_for(
            tag_id=f"{tag['id']}",
            group_id=f"{new_user['primary_gid']}",
        )
        resp = await client.delete(
            f"{url}",
        )
        await assert_status(resp, status.HTTP_204_NO_CONTENT)


@pytest.fixture
async def user_tag_id(client: TestClient) -> IdInt:
    assert client.app

    url = client.app.router["create_tag"].url_for()
    resp = await client.post(
        f"{url}",
        json={"name": "shared", "color": "#fff"},
    )
    tag, _ = await assert_status(resp, status.HTTP_201_CREATED)
    return tag["id"]


@pytest.mark.parametrize(
    "user_role", [role for role in UserRole if role >= UserRole.USER]
)
async def test_cannot_share_tag_with_everyone(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    user_tag_id: IdInt,
    _clean_tags_table: None,
):
    assert client.app
    assert UserRole(logged_user["role"]) == user_role

    # cannot SHARE with everyone group
    url = client.app.router["create_tag_group"].url_for(
        tag_id=f"{user_tag_id}", group_id=f"{EVERYONE_GROUP_ID}"
    )
    resp = await client.post(
        f"{url}",
        json={"read": True, "write": True, "delete": True},
    )
    _, error = await assert_status(resp, status.HTTP_403_FORBIDDEN)
    assert error

    # cannot REPLACE with everyone group
    url = client.app.router["replace_tag_group"].url_for(
        tag_id=f"{user_tag_id}", group_id=f"{EVERYONE_GROUP_ID}"
    )
    resp = await client.put(
        f"{url}",
        json={"read": True, "write": True, "delete": True},
    )
    _, error = await assert_status(resp, status.HTTP_403_FORBIDDEN)
    assert error

    # cannot DELETE with everyone group
    url = client.app.router["delete_tag_group"].url_for(
        tag_id=f"{user_tag_id}", group_id=f"{EVERYONE_GROUP_ID}"
    )
    resp = await client.delete(
        f"{url}",
        json={"read": True, "write": True, "delete": True},
    )
    _, error = await assert_status(resp, status.HTTP_403_FORBIDDEN)
    assert error


@pytest.mark.parametrize(
    "user_role,expected_status",
    [
        (
            role,
            # granted only to:
            (
                status.HTTP_403_FORBIDDEN
                if role < UserRole.TESTER
                else status.HTTP_201_CREATED
            ),
        )
        for role in UserRole
        if role >= UserRole.USER
    ],
)
async def test_can_only_share_tag_with_product_group_if_granted_by_role(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    user_tag_id: IdInt,
    expected_status: int,
    _clean_tags_table: None,
    product_name: ProductName,
):
    assert client.app
    assert UserRole(logged_user["role"]) == user_role

    product_group_id = get_product(client.app, product_name=product_name).group_id

    # cannot SHARE with everyone group
    url = client.app.router["create_tag_group"].url_for(
        tag_id=f"{user_tag_id}", group_id=f"{product_group_id}"
    )
    resp = await client.post(
        f"{url}",
        json={"read": True, "write": True, "delete": True},
    )
    await assert_status(resp, expected_status)
