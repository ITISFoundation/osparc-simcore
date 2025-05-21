# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Any

import pytest
import sqlalchemy as sa
from aiohttp import web
from common_library.users_enums import AccountRequestStatus
from models_library.products import ProductName
from simcore_postgres_database.models.users_details import (
    users_pre_registration_details,
)
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.users import _users_repository


async def test_create_user_pre_registration(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
):
    # Arrange
    asyncpg_engine = get_asyncpg_engine(app)

    test_email = "test.user@example.com"
    created_by_user_id = product_owner_user["id"]
    institution = "Test Institution"
    pre_registration_details: dict[str, Any] = {
        "institution": institution,
        "pre_first_name": "Test",
        "pre_last_name": "User",
    }

    # Act
    pre_registration_id = await _users_repository.create_user_pre_registration(
        asyncpg_engine,
        email=test_email,
        created_by=created_by_user_id,
        product_name=product_name,
        **pre_registration_details,
    )

    # Assert
    async with asyncpg_engine.connect() as conn:
        # Query to check if the record was inserted
        result = await conn.execute(
            sa.select(users_pre_registration_details).where(
                (users_pre_registration_details.c.pre_email == test_email)
                & (users_pre_registration_details.c.product_name == product_name)
            )
        )
        record = result.first()

        # Clean up - delete the test record
        await conn.execute(
            sa.delete(users_pre_registration_details).where(
                users_pre_registration_details.c.id == pre_registration_id
            )
        )
        await conn.commit()

    # Verify the record was created with correct values
    assert record is not None
    assert record.pre_email == test_email
    assert record.created_by == created_by_user_id
    assert record.product_name == product_name
    assert record.institution == institution


async def test_review_user_pre_registration(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
):
    # Arrange
    asyncpg_engine = get_asyncpg_engine(app)

    test_email = "review.test@example.com"
    created_by_user_id = product_owner_user["id"]
    reviewer_id = product_owner_user["id"]  # Same user as creator for this test
    institution = "Test Institution"
    pre_registration_details: dict[str, Any] = {
        "institution": institution,
        "pre_first_name": "Review",
        "pre_last_name": "Test",
    }

    # Create a pre-registration to review
    pre_registration_id = await _users_repository.create_user_pre_registration(
        asyncpg_engine,
        email=test_email,
        created_by=created_by_user_id,
        product_name=product_name,
        **pre_registration_details,
    )

    # Act - review and approve the registration
    new_status = AccountRequestStatus.APPROVED
    await _users_repository.review_user_pre_registration(
        asyncpg_engine,
        pre_registration_id=pre_registration_id,
        reviewed_by=reviewer_id,
        new_status=new_status,
    )

    # Assert - Use list_user_pre_registrations to verify
    registrations, count = await _users_repository.list_user_pre_registrations(
        asyncpg_engine,
        filter_by_pre_email=test_email,
        filter_by_product_name=product_name,
    )

    # Check count and that we found our registration
    assert count == 1
    assert len(registrations) == 1

    # Get the registration
    reg = registrations[0]

    # Verify details
    assert reg["id"] == pre_registration_id
    assert reg["pre_email"] == test_email
    assert reg["pre_first_name"] == "Review"
    assert reg["pre_last_name"] == "Test"
    assert reg["institution"] == institution
    assert reg["product_name"] == product_name
    assert reg["account_request_status"] == new_status
    assert reg["created_by"] == created_by_user_id
    assert reg["account_request_reviewed_by"] == reviewer_id
    assert reg["account_request_reviewed_at"] is not None
    assert reg["created_by_name"] == product_owner_user["name"]
    assert reg["reviewed_by_name"] == product_owner_user["name"]

    # Clean up
    async with asyncpg_engine.connect() as conn:
        await conn.execute(
            sa.delete(users_pre_registration_details).where(
                users_pre_registration_details.c.id == pre_registration_id
            )
        )
        await conn.commit()


async def test_list_user_pre_registrations(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
):
    # Arrange
    asyncpg_engine = get_asyncpg_engine(app)
    created_by_user_id = product_owner_user["id"]

    # Create multiple pre-registrations with different statuses
    emails = [
        "test1@example.com",
        "test2@example.com",
        "test3@example.com",
        "different@example.com",
    ]
    pre_reg_ids = []

    # Create pending registrations
    for i, email in enumerate(emails[:3]):
        pre_reg_id = await _users_repository.create_user_pre_registration(
            asyncpg_engine,
            email=email,
            created_by=created_by_user_id,
            product_name=product_name,
            pre_first_name=f"User{i+1}",
            pre_last_name="Test",
            institution="Test Institution",
        )
        pre_reg_ids.append(pre_reg_id)

    # Create and approve one registration
    await _users_repository.review_user_pre_registration(
        asyncpg_engine,
        pre_registration_id=pre_reg_ids[0],
        reviewed_by=created_by_user_id,
        new_status=AccountRequestStatus.APPROVED,
    )

    # Create and reject one registration
    await _users_repository.review_user_pre_registration(
        asyncpg_engine,
        pre_registration_id=pre_reg_ids[1],
        reviewed_by=created_by_user_id,
        new_status=AccountRequestStatus.REJECTED,
    )

    # The third registration remains in PENDING status

    # Act & Assert - Test different filter combinations

    # 1. Get all registrations (should be 3)
    all_registrations, count = await _users_repository.list_user_pre_registrations(
        asyncpg_engine,
        filter_by_product_name=product_name,
    )
    assert count == 3
    assert len(all_registrations) == 3

    # 2. Filter by email pattern (should match first 3 emails with "test")
    test_registrations, count = await _users_repository.list_user_pre_registrations(
        asyncpg_engine,
        filter_by_pre_email="test",
        filter_by_product_name=product_name,
    )
    assert count == 3
    assert len(test_registrations) == 3
    assert all("test" in reg["pre_email"] for reg in test_registrations)

    # 3. Filter by status - APPROVED
    approved_registrations, count = await _users_repository.list_user_pre_registrations(
        asyncpg_engine,
        filter_by_account_request_status=AccountRequestStatus.APPROVED,
        filter_by_product_name=product_name,
    )
    assert count == 1
    assert len(approved_registrations) == 1
    assert approved_registrations[0]["pre_email"] == emails[0]
    assert (
        approved_registrations[0]["account_request_status"]
        == AccountRequestStatus.APPROVED
    )

    # 4. Filter by status - REJECTED
    rejected_registrations, count = await _users_repository.list_user_pre_registrations(
        asyncpg_engine,
        filter_by_account_request_status=AccountRequestStatus.REJECTED,
        filter_by_product_name=product_name,
    )
    assert count == 1
    assert len(rejected_registrations) == 1
    assert rejected_registrations[0]["pre_email"] == emails[1]
    assert (
        rejected_registrations[0]["account_request_status"]
        == AccountRequestStatus.REJECTED
    )

    # 5. Filter by status - PENDING
    pending_registrations, count = await _users_repository.list_user_pre_registrations(
        asyncpg_engine,
        filter_by_account_request_status=AccountRequestStatus.PENDING,
        filter_by_product_name=product_name,
    )
    assert count == 1
    assert len(pending_registrations) == 1
    assert pending_registrations[0]["pre_email"] == emails[2]
    assert (
        pending_registrations[0]["account_request_status"]
        == AccountRequestStatus.PENDING
    )

    # 6. Test pagination
    paginated_registrations, count = (
        await _users_repository.list_user_pre_registrations(
            asyncpg_engine,
            filter_by_product_name=product_name,
            pagination_limit=2,
            pagination_offset=0,
        )
    )
    assert count == 3  # Still shows total count of 3
    assert len(paginated_registrations) == 2  # But only returns 2 records

    # Get next page
    page2_registrations, count = await _users_repository.list_user_pre_registrations(
        asyncpg_engine,
        filter_by_product_name=product_name,
        pagination_limit=2,
        pagination_offset=2,
    )
    assert count == 3
    assert len(page2_registrations) == 1  # Only 1 record on the second page

    # Clean up
    async with asyncpg_engine.connect() as conn:
        for pre_reg_id in pre_reg_ids:
            await conn.execute(
                sa.delete(users_pre_registration_details).where(
                    users_pre_registration_details.c.id == pre_reg_id
                )
            )
        await conn.commit()


@pytest.mark.parametrize(
    "link_to_existing_user,expected_linked", [(True, True), (False, False)]
)
async def test_create_pre_registration_with_existing_user_linking(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
    link_to_existing_user: bool,
    expected_linked: bool,
):
    """Test that creating a pre-registration for an existing user correctly handles auto-linking."""
    # Arrange
    asyncpg_engine = get_asyncpg_engine(app)
    existing_user_id = product_owner_user["id"]
    existing_user_email = product_owner_user["email"]

    # Act - Create pre-registration with the same email as product_owner_user
    pre_registration_id = await _users_repository.create_user_pre_registration(
        asyncpg_engine,
        email=existing_user_email,  # Same email as existing user
        created_by=existing_user_id,
        product_name=product_name,
        link_to_existing_user=link_to_existing_user,  # Parameter to test
        pre_first_name="Link-Test",
        pre_last_name="User",
        institution=f"{'Auto-linked' if link_to_existing_user else 'No-link'} Institution",
    )

    # Assert - Verify through list_user_pre_registrations
    registrations, count = await _users_repository.list_user_pre_registrations(
        asyncpg_engine,
        filter_by_pre_email=existing_user_email,
        filter_by_product_name=product_name,
    )

    # Verify count and that we found our registration
    assert count == 1
    assert len(registrations) == 1

    # Get the registration
    reg = registrations[0]

    # Verify linking behavior based on parameter
    assert reg["id"] == pre_registration_id
    assert reg["pre_email"] == existing_user_email

    # When True, user_id should be set to the existing user ID
    # When False, user_id should be None
    if expected_linked:
        assert (
            reg["user_id"] == existing_user_id
        ), "Should be linked to the existing user"
    else:
        assert reg["user_id"] is None, "Should NOT be linked to any user"

    # Clean up
    async with asyncpg_engine.connect() as conn:
        await conn.execute(
            sa.delete(users_pre_registration_details).where(
                users_pre_registration_details.c.id == pre_registration_id
            )
        )
        await conn.commit()
