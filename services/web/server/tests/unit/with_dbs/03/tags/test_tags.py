# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.groups import EVERYONE_GROUP_ID
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
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_projects import assert_get_same_project
from servicelib.aiohttp import status
from simcore_postgres_database.models.tags import tags
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.db.plugin import get_database_engine
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def _clean_tags_table(postgres_db: sa.engine.Engine) -> Iterator[None]:
    yield
    with postgres_db.connect() as conn:
        conn.execute(tags.delete())


@pytest.fixture
def fake_tags(faker: Faker) -> list[dict[str, Any]]:
    return [
        {"name": "tag1", "description": "description1", "color": "#f00"},
        {"name": "tag2", "description": "description2", "color": "#00f"},
    ]


@pytest.fixture
def user_role() -> UserRole:
    # All tests in test_tags assume USER's role
    # i.e. Used in `logged_user` and `user_project`
    return UserRole.USER


async def test_tags_to_studies(
    client: TestClient,
    user_project: ProjectDict,
    fake_tags: dict[str, Any],
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
):
    catalog_subsystem_mock([user_project])
    assert client.app

    # Add test tags
    added_tags = []

    for tag in fake_tags:
        url = client.app.router["create_tag"].url_for()
        resp = await client.post(f"{url}", json=tag)
        added_tag, _ = await assert_status(resp, status.HTTP_200_OK)
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
    assert user_role == UserRole.USER

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
    assert user_role == UserRole.USER

    # (1) create tag
    url = client.app.router["create_tag"].url_for()
    resp = await client.post(
        f"{url}",
        json={"name": "T", "color": "#f00"},
    )
    created, _ = await assert_status(resp, status.HTTP_200_OK)

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
    assert user_role == UserRole.USER

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
        created, _ = await assert_status(resp, status.HTTP_200_OK)
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
    resp = await client.post(
        f"{url}",
        json={"name": "New", "color": "#f00", "description": "w/o priority"},
    )
    last_created, _ = await assert_status(resp, status.HTTP_200_OK)

    url = client.app.router["list_tags"].url_for()
    resp = await client.get(f"{url}")
    got, _ = await assert_status(resp, status.HTTP_200_OK)
    assert got == [*expected_tags[::-1], last_created]


async def test_share_tags(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    everybody_tag_id: int,
    _clean_tags_table: None,
):
    assert client.app
    assert user_role == UserRole.USER

    # CREATE
    url = client.app.router["create_tag"].url_for()
    resp = await client.post(
        f"{url}",
        json={"name": "shared", "color": "#fff"},
    )
    created, _ = await assert_status(resp, status.HTTP_200_OK)

    # SHARE (all combinations)?
    url = client.app.router["create_tag_group"].url_for(
        tag_id=created["id"], group_id=f"{EVERYONE_GROUP_ID}"
    )
    resp = await client.post(
        f"{url}",
        json={"read": True, "write": False, "delete": False},
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    # test only performed allowed combinations

    # REPLACE SHARE to other combinations
    url = client.app.router["replace_tag_groups"].url_for(
        tag_id=created["id"], group_id=f"{EVERYONE_GROUP_ID}"
    )
    resp = await client.put(
        f"{url}",
        json={"read": True, "write": True, "delete": False},
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    # test can perform new combinations

    # DELETE share
    url = client.app.router["delete_tag_group"].url_for(
        tag_id=created["id"], group_id=f"{EVERYONE_GROUP_ID}"
    )
    resp = await client.delete(
        f"{url}",
    )
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    # test can do nothing
