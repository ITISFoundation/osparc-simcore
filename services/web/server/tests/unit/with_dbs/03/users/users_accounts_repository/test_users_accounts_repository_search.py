# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from typing import Any

import pytest
from aiohttp import web
from models_library.products import ProductName
from pytest_simcore.helpers.webserver_users import MixedUserTestData
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.users import _accounts_repository


@pytest.mark.parametrize(
    "email_pattern,expected_count",
    [
        ("%pre.registered%", 1),
        ("%nonexistent%", 0),
    ],
)
async def test_search_merged_users_by_email(
    app: web.Application,
    product_name: ProductName,
    mixed_user_data: MixedUserTestData,
    email_pattern: str,
    expected_count: int,
):
    """Test searching merged users by email pattern."""
    asyncpg_engine = get_asyncpg_engine(app)

    rows = await _accounts_repository.search_merged_pre_and_registered_users(
        asyncpg_engine,
        filter_by_email_like=email_pattern,
        product_name=product_name,
    )

    assert len(rows) == expected_count

    if expected_count > 0:
        row = rows[0]
        assert row.pre_email == mixed_user_data.pre_reg_email
        assert row.pre_first_name == "Pre-Registered"
        assert row.pre_last_name == "Only"
        assert row.institution == "Pre-Reg Institution"


@pytest.mark.parametrize(
    "use_valid_username,expected_count",
    [
        (True, 1),
        (False, 0),
    ],
)
async def test_search_merged_users_by_username(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
    use_valid_username: bool,
    expected_count: int,
):
    """Test searching merged users by username pattern."""
    asyncpg_engine = get_asyncpg_engine(app)

    username_pattern = f"{product_owner_user['name']}" if use_valid_username else "%nonexistent_username%"

    rows = await _accounts_repository.search_merged_pre_and_registered_users(
        asyncpg_engine,
        filter_by_user_name_like=username_pattern,
        product_name=product_name,
    )

    assert len(rows) >= expected_count

    if expected_count > 0:
        found_user = next(
            (row for row in rows if row.email == product_owner_user["email"]),
            None,
        )
        assert found_user is not None
        assert found_user.first_name == product_owner_user["first_name"]
        assert found_user.last_name == product_owner_user["last_name"]


@pytest.mark.parametrize(
    "use_valid_group_id,expected_count",
    [
        (True, 1),
        (False, 0),
    ],
)
async def test_search_merged_users_by_primary_group_id(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
    use_valid_group_id: bool,
    expected_count: int,
):
    """Test searching merged users by primary group ID."""
    asyncpg_engine = get_asyncpg_engine(app)

    primary_group_id = product_owner_user["primary_gid"] if use_valid_group_id else 99999

    results = await _accounts_repository.search_merged_pre_and_registered_users(
        asyncpg_engine,
        filter_by_primary_group_id=primary_group_id,
        product_name=product_name,
    )

    assert len(results) >= expected_count

    if expected_count > 0:
        found_user = next(
            (result for result in results if result.email == product_owner_user["email"]),
            None,
        )
        assert found_user is not None
        assert found_user.first_name == product_owner_user["first_name"]
        assert found_user.last_name == product_owner_user["last_name"]
