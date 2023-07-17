# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Any, AsyncIterator, Callable, Iterator

import pytest
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects_state import (
    ProjectLocked,
    ProjectRunningState,
    ProjectState,
    ProjectStatus,
    RunningState,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from pytest_simcore.helpers.utils_projects import assert_get_same_project
from pytest_simcore.helpers.utils_tags import create_tag, delete_tag
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


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, web.HTTPOk)])
async def test_tags_to_studies(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project,
    expected: type[web.HTTPException],
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
        added_tag, _ = await assert_status(resp, expected)
        added_tags.append(added_tag)

        # Add tag to study
        url = client.app.router["add_tag"].url_for(
            project_uuid=user_project.get("uuid"), tag_id=str(added_tag.get("id"))
        )
        resp = await client.put(f"{url}")
        data, _ = await assert_status(resp, expected)

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
    data = await assert_get_same_project(client, user_project, expected)

    # Delete tag0
    url = client.app.router["delete_tag"].url_for(tag_id=str(added_tags[0].get("id")))
    resp = await client.delete(f"{url}")
    await assert_status(resp, web.HTTPNoContent)

    # Get project and check that tag is no longer there
    user_project["tags"].remove(added_tags[0]["id"])
    data = await assert_get_same_project(client, user_project, expected)
    assert added_tags[0].get("id") not in data.get("tags")

    # Remove tag1 from project
    url = client.app.router["remove_tag"].url_for(
        project_uuid=user_project.get("uuid"), tag_id=str(added_tags[1].get("id"))
    )
    resp = await client.delete(f"{url}")
    await assert_status(resp, expected)
    # Get project and check that tag is no longer there
    user_project["tags"].remove(added_tags[1]["id"])
    data = await assert_get_same_project(client, user_project, expected)
    assert added_tags[1].get("id") not in data.get("tags")

    # Delete tag1
    url = client.app.router["delete_tag"].url_for(tag_id=str(added_tags[1].get("id")))
    resp = await client.delete(f"{url}")
    await assert_status(resp, web.HTTPNoContent)


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


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


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
    datas, _ = await assert_status(resp, web.HTTPOk)

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

    resp = await client.post(
        f"{client.app.router['create_tag'].url_for()}",
        json={"name": "T", "color": "#f00"},
    )
    created, _ = await assert_status(resp, web.HTTPOk)

    assert created == {
        "id": created["id"],
        "name": "T",
        "description": None,
        "color": "#f00",
        "accessRights": {"read": True, "write": True, "delete": True},
    }

    url = client.app.router["update_tag"].url_for(tag_id=f"{created['id']}")
    resp = await client.patch(
        f"{url}",
        json={"description": "This is my tag"},
    )

    updated, _ = await assert_status(resp, web.HTTPOk)
    created.update(description="This is my tag")
    assert updated == created

    url = client.app.router["update_tag"].url_for(tag_id=f"{everybody_tag_id}")
    resp = await client.patch(
        f"{url}",
        json={"description": "I have NO WRITE ACCESS TO THIS TAG"},
    )
    _, error = await assert_status(resp, web.HTTPUnauthorized)
    assert error
