# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
"""

Fixtures for groups

NOTE: These fixtures are used in integration and unit tests
"""


from collections.abc import AsyncIterator
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.groups import GroupGet
from models_library.groups import GroupsByTypeTuple, StandardGroupCreate
from models_library.users import UserID
from pytest_simcore.helpers.webserver_users import NewUser, UserInfoDict
from simcore_service_webserver.groups._groups_service import (
    add_user_in_group,
    create_standard_group,
    delete_standard_group,
    list_user_groups_with_read_access,
)


def _groupget_model_dump(group, access_rights) -> dict[str, Any]:
    return GroupGet.from_domain_model(group, access_rights).model_dump(
        mode="json",
        by_alias=True,
        exclude_unset=True,
    )


async def _create_organization(
    app: web.Application, user_id: UserID, new_group: dict
) -> dict[str, Any]:
    group, access_rights = await create_standard_group(
        app,
        user_id=user_id,
        create=StandardGroupCreate.model_validate(new_group),
    )
    return _groupget_model_dump(group=group, access_rights=access_rights)


#
# USER'S GROUPS FIXTURES
#


@pytest.fixture
async def standard_groups_owner(
    client: TestClient,
    logged_user: UserInfoDict,
) -> AsyncIterator[UserInfoDict]:
    """
    standard_groups_owner creates TWO organizations and adds logged_user in them
    """

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
        sparc_group = await _create_organization(
            app=client.app,
            user_id=owner_user["id"],
            new_group={
                "name": "SPARC",
                "description": "Stimulating Peripheral Activity to Relieve Conditions",
                "thumbnail": "https://commonfund.nih.gov/sites/default/files/sparc-image-homepage500px.png",
                "inclusion_rules": {"email": r"@(sparc)+\.(io|com)$"},
            },
        )
        team_black_group = await _create_organization(
            app=client.app,
            user_id=owner_user["id"],
            new_group={
                "name": "team Black",
                "description": "THE incredible black team",
                "thumbnail": None,
                "inclusion_rules": {"email": r"@(black)+\.(io|com)$"},
            },
        )

        # adds logged_user  to sparc group
        await add_user_in_group(
            app=client.app,
            user_id=owner_user["id"],
            group_id=sparc_group["gid"],
            new_by_user_id=logged_user["id"],
        )

        # adds logged_user  to team-black group
        await add_user_in_group(
            app=client.app,
            user_id=owner_user["id"],
            group_id=team_black_group["gid"],
            new_by_user_id=logged_user["id"],
        )

        yield owner_user

        # clean groups
        await delete_standard_group(
            client.app, user_id=owner_user["id"], group_id=sparc_group["gid"]
        )
        await delete_standard_group(
            client.app, user_id=owner_user["id"], group_id=team_black_group["gid"]
        )


@pytest.fixture
async def logged_user_groups_by_type(
    client: TestClient, logged_user: UserInfoDict, standard_groups_owner: UserInfoDict
) -> GroupsByTypeTuple:
    assert client.app

    assert logged_user["id"] != standard_groups_owner["id"]

    groups_by_type = await list_user_groups_with_read_access(
        client.app, user_id=logged_user["id"]
    )
    assert groups_by_type.primary
    assert groups_by_type.everyone
    return groups_by_type


@pytest.fixture
def primary_group(
    logged_user_groups_by_type: GroupsByTypeTuple,
) -> dict[str, Any]:
    """`logged_user`'s primary group"""
    assert logged_user_groups_by_type.primary
    return _groupget_model_dump(*logged_user_groups_by_type.primary)


@pytest.fixture
def standard_groups(
    logged_user_groups_by_type: GroupsByTypeTuple,
) -> list[dict[str, Any]]:
    """owned by `standard_groups_owner` and shared with `logged_user`"""
    return [_groupget_model_dump(*sg) for sg in logged_user_groups_by_type.standard]


@pytest.fixture
def all_group(
    logged_user_groups_by_type: GroupsByTypeTuple,
) -> dict[str, Any]:
    assert logged_user_groups_by_type.everyone
    return _groupget_model_dump(*logged_user_groups_by_type.everyone)
