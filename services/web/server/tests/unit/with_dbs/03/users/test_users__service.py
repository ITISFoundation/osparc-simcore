# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import AsyncIterable
from typing import Any

import pytest
import sqlalchemy as sa
from aiohttp import web
from models_library.api_schemas_webserver.users import UserAccountGet
from models_library.products import ProductName
from simcore_postgres_database.models.users_details import (
    users_pre_registration_details,
)
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.users import _users_service
from simcore_service_webserver.users._users_repository import (
    create_user_pre_registration,
)


@pytest.fixture
async def pre_registered_user_created(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
) -> AsyncIterable[dict[str, Any]]:
    """Creates a pre-registered user and returns the details.
    Automatically cleans up after the test."""

    asyncpg_engine = get_asyncpg_engine(app)
    pre_registered_email = "pre-registered@example.com"
    created_by_user_id = product_owner_user["id"]

    pre_registration_details = {
        "pre_first_name": "Pre-Registered",
        "pre_last_name": "User",
        "institution": "Test University",
        "address": "123 Test Street",
        "city": "Test City",
        "state": "Test State",
        "postal_code": "12345",
        "country": "US",
    }

    # Create a pre-registered user
    pre_registration_id = await create_user_pre_registration(
        asyncpg_engine,
        email=pre_registered_email,
        created_by=created_by_user_id,
        product_name=product_name,
        **pre_registration_details,
    )

    # Return all details including the ID for tests to use
    yield {
        "id": pre_registration_id,
        "email": pre_registered_email,
        "details": pre_registration_details,
        "creator_id": created_by_user_id,
    }

    # Clean up after test
    async with asyncpg_engine.connect() as conn:
        await conn.execute(
            sa.delete(users_pre_registration_details).where(
                users_pre_registration_details.c.id == pre_registration_id
            )
        )
        await conn.commit()


async def test_search_users_as_admin_real_user(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
):
    """Test searching for a real user as admin"""
    # Arrange
    user_email = product_owner_user["email"]

    # Act
    found_users = await _users_service.search_users_accounts(
        app, email_glob=user_email, product_name=product_name, include_products=False
    )

    # Assert
    assert len(found_users) == 1
    found_user = found_users[0]
    assert found_user.email == user_email
    assert found_user.registered is True
    assert (
        found_user.products is None
    )  # This test user does not have a product associated with it

    # Verify the UserForAdminGet model is populated correctly
    assert isinstance(found_user, UserAccountGet)
    assert found_user.first_name == product_owner_user["first_name"]


async def test_search_users_as_admin_pre_registered_user(
    app: web.Application,
    product_name: ProductName,
    pre_registered_user_created: dict[str, Any],
):
    """Test searching for a pre-registered user as admin"""
    # Arrange
    pre_registered_email = pre_registered_user_created["email"]
    pre_registration_details = pre_registered_user_created["details"]

    # Act
    found_users = await _users_service.search_users_accounts(
        app, email_glob=pre_registered_email, product_name=product_name
    )

    # Assert
    assert len(found_users) == 1
    pre_registered_user_found = found_users[0]
    assert pre_registered_user_found.email == pre_registered_email
    assert (
        pre_registered_user_found.registered is False
    )  # Pre-registered users are not yet registered
    assert (
        pre_registered_user_found.institution == pre_registration_details["institution"]
    )
    assert (
        pre_registered_user_found.first_name
        == pre_registration_details["pre_first_name"]
    )
    assert (
        pre_registered_user_found.last_name == pre_registration_details["pre_last_name"]
    )
    assert pre_registered_user_found.address == pre_registration_details["address"]

    # Verify the invited_by field is populated (should be the name of the product owner)
    assert pre_registered_user_found.invited_by is not None


async def test_search_users_as_admin_wildcard(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
    pre_registration_details_db_cleanup: None,
):
    """Test searching for users with wildcards"""
    # Arrange
    asyncpg_engine = get_asyncpg_engine(app)
    email_domain = "@example.com"

    # Create multiple pre-registered users with the same domain
    emails = [f"user1{email_domain}", f"user2{email_domain}", "different@other.com"]
    created_by_user_id = product_owner_user["id"]

    # Create pre-registered users
    for email in emails:
        await create_user_pre_registration(
            asyncpg_engine,
            email=email,
            created_by=created_by_user_id,
            product_name=product_name,
            institution="Test Institution",
        )

    # Act - search with wildcard for the domain
    found_users = await _users_service.search_users_accounts(
        app, email_glob=f"*{email_domain}", product_name=product_name
    )

    # Assert
    assert len(found_users) == 2  # Should find the two users with @example.com
    emails_found = [user.email for user in found_users]
    assert f"user1{email_domain}" in emails_found
    assert f"user2{email_domain}" in emails_found
    assert "different@other.com" not in emails_found
