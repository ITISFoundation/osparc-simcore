from collections.abc import Awaitable, Callable

import pytest
from aiohttp.test_utils import TestClient
from models_library.users import UserID
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.postgres_tags import create_tag_access
from pytest_simcore.helpers.webserver_users import NewUser, UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.tags import tags_service
from simcore_service_webserver.tags.schemas import TagCreate

pytest_simcore_core_services_selection = ["postgres", "redis", "rabbit"]
pytestmark = pytest.mark.usefixtures(
    "mock_dynamic_scheduler", "mocked_dynamic_services_interface", "storage_subsystem_mock", "project_db_cleaner"
)


@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize(
    "selection", ["omitted", "empty", "empty-source-default", "selected", "selected-overlap"], ids=str
)
@pytest.mark.parametrize("minimal_copy_override", [False, True], ids=["full-body", "copy-override"])
@pytest.mark.parametrize("as_template", [False, True], ids=["study", "template"])
async def test_copy_project_applies_selected_tags_before_defaults(
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group: dict[str, str],
    user_project: ProjectDict,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
    selection: str,
    minimal_copy_override: bool,
    as_template: bool,
):
    assert client.app
    tag_ids = []
    for name in ("source", "selected", "default"):
        response = await client.post(client.app.router["create_tag"].url_for(), json={"name": name, "color": "#336699"})
        tag, _ = await assert_status(response, status.HTTP_201_CREATED)
        tag_ids.append(tag["id"])
    source_id = tag_ids[0]
    selected_id = tag_ids[1]
    default_id = source_id if selection == "empty-source-default" else tag_ids[2]
    response = await client.post(
        client.app.router["add_project_tag"].url_for(project_uuid=user_project["uuid"], tag_id=f"{source_id}")
    )
    await assert_status(response, status.HTTP_200_OK)
    response = await client.patch(
        client.app.router["set_frontend_preference"].url_for(preference_id="defaultStudyTagIds"),
        json={"value": [default_id]},
    )
    await assert_status(response, status.HTTP_204_NO_CONTENT)

    overrides = {
        "omitted": {"name": "Copied study"},
        "empty": {"tags": []},
        "empty-source-default": {"tags": []},
        "selected": {"tags": [selected_id]},
        "selected-overlap": {"tags": [selected_id, default_id]},
    }
    expected = {
        "omitted": [source_id] if as_template else [source_id, default_id],
        "empty": [] if as_template else [default_id],
        "empty-source-default": [] if as_template else [default_id],
        "selected": [selected_id] if as_template else [selected_id, default_id],
        "selected-overlap": [selected_id, default_id],
    }
    project = await request_create_project(
        client,
        status.HTTP_202_ACCEPTED,
        status.HTTP_201_CREATED,
        logged_user,
        primary_group,
        from_study=user_project,
        project=overrides[selection],
        expected_tags=expected[selection],
        minimal_copy_override=minimal_copy_override,
        as_template=as_template,
    )
    assert project["tags"] == expected[selection]


@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize(
    "minimal_copy_override",
    [False, True],
    ids=["copy-full-body", "copy-override"],
)
@pytest.mark.parametrize("tag_kind", ["inaccessible", "missing"], ids=str)
async def test_copy_project_rejects_unavailable_explicit_tags(
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group: dict[str, str],
    user_project: ProjectDict,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
    minimal_copy_override: bool,
    tag_kind: str,
):
    assert client.app
    async with NewUser(app=client.app) as other_user:
        tag = await tags_service.create_tag(
            client.app, UserID(other_user["id"]), TagCreate(name="private", color="#336699")
        )
        tag_id = tag.id if tag_kind == "inaccessible" else 2_147_483_647
        project = await request_create_project(
            client,
            status.HTTP_202_ACCEPTED,
            status.HTTP_400_BAD_REQUEST,
            logged_user,
            primary_group,
            project={"tags": [tag_id]},
            from_study=user_project,
            minimal_copy_override=minimal_copy_override,
        )
        assert project == {}


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_copy_project_accepts_read_only_shared_tag(
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group: dict[str, str],
    user_project: ProjectDict,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
):
    assert client.app
    async with NewUser(app=client.app) as other_user:
        tag = await tags_service.create_tag(
            client.app, UserID(other_user["id"]), TagCreate(name="shared", color="#336699")
        )
        async with get_asyncpg_engine(client.app).begin() as conn:
            await create_tag_access(
                conn,
                tag_id=tag.id,
                group_id=logged_user["primary_gid"],
                read=True,
                write=False,
                delete=False,
            )
        project = await request_create_project(
            client,
            status.HTTP_202_ACCEPTED,
            status.HTTP_201_CREATED,
            logged_user,
            primary_group,
            project={"tags": [tag.id]},
            from_study=user_project,
            minimal_copy_override=True,
            expected_tags=[tag.id],
        )
        assert project["tags"] == [tag.id]


@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize("explicit", [False, True], ids=["omitted", "explicit"])
async def test_copy_project_preserves_inaccessible_source_tag(
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group: dict[str, str],
    user_project: ProjectDict,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
    explicit: bool,
):
    assert client.app
    async with NewUser(app=client.app) as other_user:
        tag = await tags_service.create_tag(
            client.app,
            UserID(other_user["id"]),
            TagCreate(name="private source tag", color="#336699"),
        )
        response = await client.post(
            client.app.router["add_project_tag"].url_for(project_uuid=user_project["uuid"], tag_id=f"{tag.id}")
        )
        await assert_status(response, status.HTTP_200_OK)
        project = await request_create_project(
            client,
            status.HTTP_202_ACCEPTED,
            status.HTTP_201_CREATED,
            logged_user,
            primary_group,
            from_study=user_project,
            project={"tags": [tag.id]} if explicit else {"name": "Copy"},
            minimal_copy_override=True,
            expected_tags=[tag.id],
        )
        assert project["tags"] == [tag.id]
