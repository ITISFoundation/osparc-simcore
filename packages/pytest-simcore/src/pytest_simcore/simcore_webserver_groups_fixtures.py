# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
"""

    Fixtures for groups

    NOTE: These fixtures are used in integration and unit tests
"""


from collections.abc import AsyncIterator
from typing import Any, Protocol

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.groups import GroupGet
from models_library.groups import GroupsByTypeTuple
from models_library.users import UserID
from pytest_simcore.helpers.webserver_login import NewUser, UserInfoDict
from simcore_service_webserver.groups import _groups_db
from simcore_service_webserver.groups._groups_api import (
    add_user_in_group,
    delete_organization,
    list_user_groups_with_read_access,
)


def _to_group_get_json(group, access_rights) -> dict[str, Any]:
    return GroupGet.from_model(group, access_rights).model_dump(mode="json")


#
# FACTORY FIXTURES
#


class CreateUserGroupCallable(Protocol):
    async def __call__(
        self, app: web.Application, user_id: UserID, new_group: dict
    ) -> dict[str, Any]:
        ...


@pytest.fixture
def create_user_group() -> CreateUserGroupCallable:
    async def _create(
        app: web.Application, user_id: UserID, new_group: dict
    ) -> dict[str, Any]:
        group, access_rights = await _groups_db.create_user_group(
            app, user_id=user_id, new_group=new_group
        )
        return _to_group_get_json(group=group, access_rights=access_rights)

    return _create


#
# USER'S GROUPS FIXTURES
#


@pytest.fixture
async def logged_user_groups_by_type(
    client: TestClient, logged_user: UserInfoDict
) -> GroupsByTypeTuple:
    assert client.app

    groups_by_type = await list_user_groups_with_read_access(
        client.app, user_id=logged_user["id"]
    )
    assert groups_by_type.primary
    assert groups_by_type.everyone
    return groups_by_type


@pytest.fixture
async def primary_group(
    client: TestClient,
    logged_user_groups_by_type: GroupsByTypeTuple,
) -> dict[str, Any]:
    assert client.app
    assert logged_user_groups_by_type.primary
    return _to_group_get_json(*logged_user_groups_by_type.primary)


@pytest.fixture
async def standard_groups(
    client: TestClient,
    logged_user: UserInfoDict,
    logged_user_groups_by_type: GroupsByTypeTuple,
    create_user_group: CreateUserGroupCallable,
) -> AsyncIterator[list[dict[str, Any]]]:

    assert client.app
    # create a separate account to own standard groups
    async with NewUser(
        {
            "name": f"{logged_user['name']}_groups_owner",
            "role": "USER",
        },
        client.app,
    ) as owner_user:
        # creates two groups
        sparc_group = await create_user_group(
            app=client.app,
            user_id=owner_user["id"],
            new_group={
                "label": "SPARC",
                "description": "Stimulating Peripheral Activity to Relieve Conditions",
                "thumbnail": "https://commonfund.nih.gov/sites/default/files/sparc-image-homepage500px.png",
                "inclusionRules": {"email": r"@(sparc)+\.(io|com)$"},
            },
        )
        team_black_group = await create_user_group(
            app=client.app,
            user_id=owner_user["id"],
            new_group={
                "gid": "5",  # this will be replaced
                "label": "team Black",
                "description": "THE incredible black team",
                "thumbnail": None,
                "inclusionRules": {"email": r"@(black)+\.(io|com)$"},
            },
        )

        # adds logged_user  to sparc group
        await add_user_in_group(
            app=client.app,
            user_id=owner_user["id"],
            gid=sparc_group["gid"],
            new_user_id=logged_user["id"],
        )

        # adds logged_user  to team-black group
        await add_user_in_group(
            app=client.app,
            user_id=owner_user["id"],
            gid=team_black_group["gid"],
            new_user_email=logged_user["email"],
        )

        standard_groups = [
            _to_group_get_json(*sg) for sg in logged_user_groups_by_type.standard
        ]

        yield standard_groups

        # clean groups
        await delete_organization(
            client.app, user_id=owner_user["id"], group_id=sparc_group["gid"]
        )
        await delete_organization(
            client.app, user_id=owner_user["id"], group_id=team_black_group["gid"]
        )


@pytest.fixture
async def all_group(
    client: TestClient,
    logged_user_groups_by_type: GroupsByTypeTuple,
) -> dict[str, Any]:
    assert client.app
    assert logged_user_groups_by_type.everyone

    return _to_group_get_json(*logged_user_groups_by_type.everyone)
