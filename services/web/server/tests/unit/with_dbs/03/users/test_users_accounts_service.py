# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import AsyncIterable
from typing import Any

import pytest
import sqlalchemy as sa
from aiohttp import web
from common_library.users_enums import AccountRequestStatus
from models_library.api_schemas_webserver.users import UserAccountGet
from models_library.products import ProductName
from simcore_postgres_database.models.users_details import (
    users_pre_registration_details,
)
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.products import products_service
from simcore_service_webserver.products.errors import ProductNotFoundError
from simcore_service_webserver.users import _accounts_service
from simcore_service_webserver.users._accounts_repository import (
    create_user_pre_registration,
)
from simcore_service_webserver.users.exceptions import (
    PreRegistrationAlreadyLinkedToAccountError,
    PreRegistrationAlreadyReviewedError,
    PreRegistrationDuplicateInProductError,
    PreRegistrationNotFoundError,
)


async def _get_other_existing_product_name(
    app: web.Application,
    *,
    current_product_name: ProductName,
) -> ProductName:
    product_names = await products_service.list_products_names(app)
    for name in product_names:
        if name != current_product_name:
            return name

    pytest.skip("At least two products are required for move-product tests")


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

    pre_registration_details: dict[str, Any] = {
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
            sa.delete(users_pre_registration_details).where(users_pre_registration_details.c.id == pre_registration_id)
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
    found_users = await _accounts_service.search_users_accounts(
        app,
        filter_by_email_glob=user_email,
        product_name=product_name,
        include_products=False,
    )

    # Assert
    assert len(found_users) == 1
    found_user = found_users[0]
    assert found_user.email == user_email
    assert found_user.registered is True
    assert found_user.products is None  # This test user does not have a product associated with it

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
    found_users = await _accounts_service.search_users_accounts(
        app, filter_by_email_glob=pre_registered_email, product_name=product_name
    )

    # Assert
    assert len(found_users) == 1
    pre_registered_user_found = found_users[0]
    assert pre_registered_user_found.email == pre_registered_email
    assert pre_registered_user_found.registered is False  # Pre-registered users are not yet registered
    assert pre_registered_user_found.institution == pre_registration_details["institution"]
    assert pre_registered_user_found.first_name == pre_registration_details["pre_first_name"]
    assert pre_registered_user_found.last_name == pre_registration_details["pre_last_name"]
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
    found_users = await _accounts_service.search_users_accounts(
        app, filter_by_email_glob=f"*{email_domain}", product_name=product_name
    )

    # Assert
    assert len(found_users) == 2  # Should find the two users with @example.com
    emails_found = [user.email for user in found_users]
    assert f"user1{email_domain}" in emails_found
    assert f"user2{email_domain}" in emails_found
    assert "different@other.com" not in emails_found


async def test_move_user_account_request_to_product_happy_path(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
):
    asyncpg_engine = get_asyncpg_engine(app)
    email = "move-happy@example.com"
    source_product = product_name
    target_product = await _get_other_existing_product_name(app, current_product_name=source_product)

    pre_registration_id = await create_user_pre_registration(
        asyncpg_engine,
        email=email,
        created_by=product_owner_user["id"],
        product_name=source_product,
        institution="Move University",
    )

    await _accounts_service.move_user_account_request_to_product(
        app,
        pre_registration_id=pre_registration_id,
        new_product_name=target_product,
        moved_by=product_owner_user["id"],
    )

    async with asyncpg_engine.connect() as conn:
        result = await conn.execute(
            sa.select(
                users_pre_registration_details.c.product_name,
                users_pre_registration_details.c.extras,
            ).where(users_pre_registration_details.c.id == pre_registration_id)
        )
        row = result.one()

    assert row.product_name == target_product
    assert row.extras
    assert "product_move" in row.extras
    move_audit = row.extras["product_move"]
    if isinstance(move_audit, list):
        move_audit = move_audit[-1]
    assert move_audit["source"] == "po_center:move_product"
    assert move_audit["confidence"] == "high"
    assert "Moved from" in move_audit["notes"]
    assert "executed_at" in move_audit


async def test_move_user_account_request_to_product_fails_if_pre_registration_not_found(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
):
    """Test moving a non-existent pre-registration raises PreRegistrationNotFoundError."""
    target_product = await _get_other_existing_product_name(app, current_product_name=product_name)
    non_existent_id = 99999

    with pytest.raises(PreRegistrationNotFoundError):
        await _accounts_service.move_user_account_request_to_product(
            app,
            pre_registration_id=non_existent_id,
            new_product_name=target_product,
            moved_by=product_owner_user["id"],
        )


async def test_move_user_account_request_to_product_fails_if_target_product_not_found(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
):
    """Test moving pre-registration to non-existent product raises ProductNotFoundError."""
    asyncpg_engine = get_asyncpg_engine(app)
    email = "move-invalid-product@example.com"
    invalid_product_name = "non-existent-product-xyz"

    pre_registration_id = await create_user_pre_registration(
        asyncpg_engine,
        email=email,
        created_by=product_owner_user["id"],
        product_name=product_name,
        institution="Test University",
    )

    with pytest.raises(ProductNotFoundError):
        await _accounts_service.move_user_account_request_to_product(
            app,
            pre_registration_id=pre_registration_id,
            new_product_name=invalid_product_name,
            moved_by=product_owner_user["id"],
        )


async def test_move_user_account_request_to_product_fails_if_reviewed(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
):
    asyncpg_engine = get_asyncpg_engine(app)
    pre_registration_id = await create_user_pre_registration(
        asyncpg_engine,
        email="move-reviewed@example.com",
        created_by=product_owner_user["id"],
        product_name=product_name,
        institution="Reviewed University",
    )

    async with asyncpg_engine.connect() as conn:
        await conn.execute(
            users_pre_registration_details.update()
            .values(account_request_status=AccountRequestStatus.APPROVED)
            .where(users_pre_registration_details.c.id == pre_registration_id)
        )
        await conn.commit()

    with pytest.raises(PreRegistrationAlreadyReviewedError):
        await _accounts_service.move_user_account_request_to_product(
            app,
            pre_registration_id=pre_registration_id,
            new_product_name=product_name,
            moved_by=product_owner_user["id"],
        )


async def test_move_user_account_request_to_product_fails_if_linked(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
):
    asyncpg_engine = get_asyncpg_engine(app)
    target_product = await _get_other_existing_product_name(app, current_product_name=product_name)

    # Create pre-reg WITHOUT auto-linking so status stays PENDING
    pre_registration_id = await create_user_pre_registration(
        asyncpg_engine,
        email="linked-pending@example.com",
        created_by=product_owner_user["id"],
        product_name=product_name,
        institution="Linked University",
        link_to_existing_user=False,
    )

    # Manually set user_id while keeping status=PENDING to simulate
    # a pre-registration linked to an account but not yet reviewed
    async with asyncpg_engine.connect() as conn:
        await conn.execute(
            users_pre_registration_details.update()
            .values(user_id=product_owner_user["id"])
            .where(users_pre_registration_details.c.id == pre_registration_id)
        )
        await conn.commit()

    with pytest.raises(PreRegistrationAlreadyLinkedToAccountError):
        await _accounts_service.move_user_account_request_to_product(
            app,
            pre_registration_id=pre_registration_id,
            new_product_name=target_product,
            moved_by=product_owner_user["id"],
        )


async def test_move_user_account_request_to_product_fails_on_duplicate_target(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
):
    asyncpg_engine = get_asyncpg_engine(app)
    email = "duplicate-move@example.com"
    target_product = await _get_other_existing_product_name(app, current_product_name=product_name)

    source_pre_registration_id = await create_user_pre_registration(
        asyncpg_engine,
        email=email,
        created_by=product_owner_user["id"],
        product_name=product_name,
        institution="Source University",
    )
    await create_user_pre_registration(
        asyncpg_engine,
        email=email,
        created_by=product_owner_user["id"],
        product_name=target_product,
        institution="Target University",
    )

    with pytest.raises(PreRegistrationDuplicateInProductError):
        await _accounts_service.move_user_account_request_to_product(
            app,
            pre_registration_id=source_pre_registration_id,
            new_product_name=target_product,
            moved_by=product_owner_user["id"],
        )
