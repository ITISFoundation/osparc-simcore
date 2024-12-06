# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
"""

    Fixtures for user groups

    NOTE: These fixtures are used in integration and unit tests
"""


from collections.abc import AsyncIterator
from typing import Any

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.groups import GroupGet
from pytest_simcore.helpers.webserver_login import NewUser, UserInfoDict
from simcore_service_webserver.groups._common.types import GroupsByTypeTuple
from simcore_service_webserver.groups._groups_api import (
    list_user_groups_with_read_access,
)
from simcore_service_webserver.groups.api import (
    add_user_in_group,
    create_user_group,
    delete_user_group,
)


def _to_group_get_json(group, access_rights) -> dict[str, Any]:
    return GroupGet.model_validate(
        {
            **group.model_dump(),
            "access_rights": access_rights,
        }
    ).model_dump(mode="json")


@pytest.fixture
async def logged_user_groups_by_type(
    client: TestClient, logged_user: UserInfoDict
) -> GroupsByTypeTuple:
    assert client.app

    groups_by_type = await list_user_groups_with_read_access(
        client.app, logged_user["id"]
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
) -> AsyncIterator[list[dict[str, Any]]]:

    assert client.app
    sparc_group = {
        "gid": "5",  # this will be replaced
        "label": "SPARC",
        "description": "Stimulating Peripheral Activity to Relieve Conditions",
        "thumbnail": "https://commonfund.nih.gov/sites/default/files/sparc-image-homepage500px.png",
        "inclusionRules": {"email": r"@(sparc)+\.(io|com)$"},
    }
    team_black_group = {
        "gid": "5",  # this will be replaced
        "label": "team Black",
        "description": "THE incredible black team",
        "thumbnail": None,
        "inclusionRules": {"email": r"@(black)+\.(io|com)$"},
    }

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
            new_group=sparc_group,
        )
        team_black_group = await create_user_group(
            app=client.app,
            user_id=owner_user["id"],
            new_group=team_black_group,
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
        await delete_user_group(client.app, owner_user["id"], sparc_group["gid"])
        await delete_user_group(client.app, owner_user["id"], team_black_group["gid"])


@pytest.fixture
async def all_group(
    client: TestClient,
    logged_user_groups_by_type: GroupsByTypeTuple,
) -> dict[str, Any]:
    assert client.app
    assert logged_user_groups_by_type.everyone

    return _to_group_get_json(*logged_user_groups_by_type.everyone)
