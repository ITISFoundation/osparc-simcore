# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import operator
from contextlib import AsyncExitStack

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.groups import GroupGet, MyGroupsGet
from pydantic import TypeAdapter
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.faker_factories import random_product
from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    standard_role_response,
)
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.groups import groups, user_to_groups
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver._meta import API_VTAG
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_groups_access_rights(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    assert client.app
    url = client.app.router["list_groups"].url_for()
    assert f"{url}" == f"/{API_VTAG}/groups"

    response = await client.get(f"{url}")
    await assert_status(response, expected.ok if user_role != UserRole.GUEST else status.HTTP_200_OK)

    url = client.app.router["create_group"].url_for()
    assert f"{url}" == f"/{API_VTAG}/groups"
    resp = await client.post(
        f"{url}",
        json={"label": "Black Sabbath", "description": "The founders of Rock'N'Roll"},
    )
    await assert_status(resp, expected.created)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_list_user_groups_and_try_modify_organizations(
    client: TestClient,
    user_role: UserRole,
    standard_groups_owner: UserInfoDict,
    logged_user: UserInfoDict,
    primary_group: dict[str, str],
    standard_groups: list[dict[str, str]],
    all_group: dict[str, str],
):
    assert client.app
    assert logged_user["id"] != standard_groups_owner["id"]
    assert logged_user["role"] == user_role

    # List all groups (organizations, primary, everyone and products) I belong to
    url = client.app.router["list_groups"].url_for()
    assert f"{url}" == f"/{API_VTAG}/groups"

    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)

    my_groups = MyGroupsGet.model_validate(data)
    assert not error

    assert my_groups.me.model_dump(by_alias=True, exclude_unset=True) == primary_group
    assert my_groups.all.model_dump(by_alias=True, exclude_unset=True) == all_group

    assert my_groups.organizations
    assert len(my_groups.organizations) == len(standard_groups)

    by_gid = operator.itemgetter("gid")
    assert sorted(
        TypeAdapter(list[GroupGet]).dump_python(
            my_groups.organizations, mode="json", by_alias=True, exclude_unset=True
        ),
        key=by_gid,
    ) == sorted(standard_groups, key=by_gid)

    for i, group in enumerate(standard_groups):
        # try to delete a group
        url = client.app.router["delete_group"].url_for(gid=f"{group['gid']}")
        response = await client.delete(f"{url}")
        await assert_status(response, status.HTTP_403_FORBIDDEN)

        # try to add some user in the group
        url = client.app.router["add_group_user"].url_for(gid=f"{group['gid']}")

        params = {"uid": logged_user["id"]} if i % 2 == 0 else {"userName": logged_user["name"]}

        response = await client.post(f"{url}", json=params)
        await assert_status(response, status.HTTP_403_FORBIDDEN)

        # try to modify the user in the group
        url = client.app.router["update_group_user"].url_for(gid=f"{group['gid']}", uid=f"{logged_user['id']}")
        response = await client.patch(
            f"{url}",
            json={"accessRights": {"read": True, "write": True, "delete": True}},
        )
        await assert_status(response, status.HTTP_403_FORBIDDEN)

        # try to remove the user from the group
        url = client.app.router["delete_group_user"].url_for(gid=f"{group['gid']}", uid=f"{logged_user['id']}")
        response = await client.delete(f"{url}")
        await assert_status(response, status.HTTP_403_FORBIDDEN)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_group_creation_workflow(
    client: TestClient,
    user_role: UserRole,
    logged_user: UserInfoDict,
):
    assert client.app
    assert logged_user["id"] != 0
    assert logged_user["role"] == user_role

    url = client.app.router["create_group"].url_for()
    new_group_data = {
        "label": "Black Sabbath",
        "description": "The founders of Rock'N'Roll",
        "thumbnail": "https://www.startpage.com/av/proxy-image?piurl=https%3A%2F%2Fencrypted-tbn0.gstatic.com%2Fimages%3Fq%3Dtbn%3AANd9GcS3pAUISv_wtYDL9Ih4JtUfAWyHj9PkYMlEBGHJsJB9QlTZuuaK%26s&sp=1591105967T00f0b7ff95c7b3bca035102fa1ead205ab29eb6cd95acedcedf6320e64634f0c",
    }

    resp = await client.post(f"{url}", json=new_group_data)
    data, error = await assert_status(resp, status.HTTP_201_CREATED)

    assert not error
    group = GroupGet.model_validate(data)

    # we get a new gid and the rest keeps the same
    assert group.model_dump(include={"label", "description", "thumbnail"}, mode="json") == new_group_data

    # we get full ownership (i.e all rights) on the group since we are the creator
    assert group.access_rights.model_dump() == {
        "read": True,
        "write": True,
        "delete": True,
    }

    # get the groups and check we are part of this new group
    url = client.app.router["list_groups"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    my_groups = MyGroupsGet.model_validate(data)
    assert my_groups.organizations
    assert len(my_groups.organizations) == 1
    assert my_groups.organizations[0].model_dump(include=set(new_group_data), mode="json") == new_group_data

    # check getting one group
    url = client.app.router["get_group"].url_for(gid=f"{group.gid}")
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    got_group = GroupGet.model_validate(data)
    assert got_group == group

    # modify the group
    url = client.app.router["update_group"].url_for(gid=f"{group.gid}")
    resp = await client.patch(f"{url}", json={"label": "Led Zeppelin"})
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    updated_group = GroupGet.model_validate(data)
    assert updated_group.model_dump(exclude={"label"}) == got_group.model_dump(exclude={"label"})
    assert updated_group.label == "Led Zeppelin"

    # check getting the group returns the newly modified group
    url = client.app.router["get_group"].url_for(gid=f"{updated_group.gid}")
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    got_group = GroupGet.model_validate(data)
    assert got_group == updated_group

    # delete the group
    url = client.app.router["delete_group"].url_for(gid=f"{updated_group.gid}")
    resp = await client.delete(f"{url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # check deleting the same group again fails
    url = client.app.router["delete_group"].url_for(gid=f"{updated_group.gid}")
    resp = await client.delete(f"{url}")
    _, error = await assert_status(resp, status.HTTP_404_NOT_FOUND)

    assert f"{group.gid}" in error["message"]

    # check getting the group fails
    url = client.app.router["get_group"].url_for(gid=f"{updated_group.gid}")
    resp = await client.get(f"{url}")
    _, error = await assert_status(resp, status.HTTP_404_NOT_FOUND)

    assert f"{group.gid}" in error["message"]


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_list_user_groups_excludes_other_product_support_group(
    client: TestClient,
    user_role: UserRole,
    logged_user: UserInfoDict,
    asyncpg_engine: AsyncEngine,
):
    assert client.app
    assert logged_user["role"] == user_role

    async with AsyncExitStack() as stack:
        other_product_group = await stack.enter_async_context(
            insert_and_get_row_lifespan(
                asyncpg_engine,
                table=groups,
                values={
                    "name": "other-product-membership-group",
                    "description": "Membership group for another product",
                    "type": "STANDARD",
                },
                pk_col=groups.c.gid,
            )
        )
        other_product_group_gid = other_product_group["gid"]

        other_product_support_group = await stack.enter_async_context(
            insert_and_get_row_lifespan(
                asyncpg_engine,
                table=groups,
                values={
                    "name": "other-product-support-group",
                    "description": "Support group for another product",
                    "type": "STANDARD",
                },
                pk_col=groups.c.gid,
            )
        )
        other_product_support_group_gid = other_product_support_group["gid"]

        await stack.enter_async_context(
            insert_and_get_row_lifespan(
                asyncpg_engine,
                table=user_to_groups,
                values={
                    "uid": logged_user["id"],
                    "gid": other_product_support_group_gid,
                    "access_rights": {"read": True, "write": False, "delete": False},
                },
                pk_cols=[user_to_groups.c.uid, user_to_groups.c.gid],
            )
        )

        other_product_data = random_product(
            name="other-product",
            priority=999,
            group_id=other_product_group_gid,
            support_standard_group_id=other_product_support_group_gid,
        )
        await stack.enter_async_context(
            insert_and_get_row_lifespan(
                asyncpg_engine,
                table=products,
                values=other_product_data,
                pk_col=products.c.name,
            )
        )

        # ACT
        url = client.app.router["list_groups"].url_for()
        response = await client.get(f"{url}")
        data, _ = await assert_status(response, status.HTTP_200_OK)
        my_groups = MyGroupsGet.model_validate(data)

        # ASSERT
        organization_ids = {group.gid for group in my_groups.organizations or []}
        assert other_product_support_group_gid not in organization_ids
