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
from pytest_simcore.helpers.webserver_users import MixedUserTestData
from simcore_postgres_database.models.users_details import (
    users_pre_registration_details,
)
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.users import _accounts_repository


async def test_list_user_pre_registrations(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
    pre_registration_details_db_cleanup: list[int],
):
    asyncpg_engine = get_asyncpg_engine(app)
    created_by_user_id = product_owner_user["id"]

    emails = [
        "test1@example.com",
        "test2@example.com",
        "test3@example.com",
        "different@example.com",
    ]
    pre_reg_ids = []

    for i, email in enumerate(emails[:3]):
        pre_reg_id = await _accounts_repository.create_user_pre_registration(
            asyncpg_engine,
            email=email,
            created_by=created_by_user_id,
            product_name=product_name,
            pre_first_name=f"User{i + 1}",
            pre_last_name="Test",
            institution="Test Institution",
        )
        pre_reg_ids.append(pre_reg_id)
        pre_registration_details_db_cleanup.append(pre_reg_id)

    await _accounts_repository.review_user_pre_registration(
        asyncpg_engine,
        pre_registration_id=pre_reg_ids[0],
        reviewed_by=created_by_user_id,
        new_status=AccountRequestStatus.APPROVED,
    )

    await _accounts_repository.review_user_pre_registration(
        asyncpg_engine,
        pre_registration_id=pre_reg_ids[1],
        reviewed_by=created_by_user_id,
        new_status=AccountRequestStatus.REJECTED,
    )

    # 1. Get all registrations (should be 3)
    all_registrations, count = await _accounts_repository.list_user_pre_registrations(
        asyncpg_engine,
        filter_by_product_name=product_name,
    )
    assert count == 3
    assert len(all_registrations) == 3

    # 2. Filter by email pattern
    test_registrations, count = await _accounts_repository.list_user_pre_registrations(
        asyncpg_engine,
        filter_by_pre_email="test",
        filter_by_product_name=product_name,
    )
    assert count == 3
    assert len(test_registrations) == 3
    assert all("test" in reg["pre_email"] for reg in test_registrations)

    # 3. Filter by status - APPROVED
    approved_registrations, count = await _accounts_repository.list_user_pre_registrations(
        asyncpg_engine,
        filter_by_account_request_status=AccountRequestStatus.APPROVED,
        filter_by_product_name=product_name,
    )
    assert count == 1
    assert len(approved_registrations) == 1
    assert approved_registrations[0]["pre_email"] == emails[0]
    assert approved_registrations[0]["account_request_status"] == AccountRequestStatus.APPROVED

    # 4. Filter by status - REJECTED
    rejected_registrations, count = await _accounts_repository.list_user_pre_registrations(
        asyncpg_engine,
        filter_by_account_request_status=AccountRequestStatus.REJECTED,
        filter_by_product_name=product_name,
    )
    assert count == 1
    assert len(rejected_registrations) == 1
    assert rejected_registrations[0]["pre_email"] == emails[1]
    assert rejected_registrations[0]["account_request_status"] == AccountRequestStatus.REJECTED

    # 5. Filter by status - PENDING
    pending_registrations, count = await _accounts_repository.list_user_pre_registrations(
        asyncpg_engine,
        filter_by_account_request_status=AccountRequestStatus.PENDING,
        filter_by_product_name=product_name,
    )
    assert count == 1
    assert len(pending_registrations) == 1
    assert pending_registrations[0]["pre_email"] == emails[2]
    assert pending_registrations[0]["account_request_status"] == AccountRequestStatus.PENDING

    # 6. Test pagination
    paginated_registrations, count = await _accounts_repository.list_user_pre_registrations(
        asyncpg_engine,
        filter_by_product_name=product_name,
        pagination_limit=2,
        pagination_offset=0,
    )
    assert count == 3
    assert len(paginated_registrations) == 2

    page2_registrations, count = await _accounts_repository.list_user_pre_registrations(
        asyncpg_engine,
        filter_by_product_name=product_name,
        pagination_limit=2,
        pagination_offset=2,
    )
    assert count == 3
    assert len(page2_registrations) == 1

    # Clean up
    async with asyncpg_engine.connect() as conn:
        for pre_reg_id in pre_reg_ids:
            await conn.execute(
                sa.delete(users_pre_registration_details).where(users_pre_registration_details.c.id == pre_reg_id)
            )
        await conn.commit()


async def test_list_merged_users_all_users(
    app: web.Application,
    product_name: ProductName,
    mixed_user_data: MixedUserTestData,
):
    """Test that list_merged_pre_and_registered_users correctly returns all users."""
    asyncpg_engine = get_asyncpg_engine(app)

    users_list, total_count = await _accounts_repository.list_merged_pre_and_registered_users(
        asyncpg_engine,
        product_name=product_name,
        filter_include_deleted=False,
        pagination_limit=10,
        pagination_offset=0,
    )

    assert total_count >= 3, "Should have at least 3 users"

    expected_emails = {
        mixed_user_data.pre_reg_email,
        mixed_user_data.product_owner_email,
        mixed_user_data.approved_email,
    }

    found_emails = {user["email"] for user in users_list}
    assert expected_emails.issubset(found_emails), "All expected users should be in results"


async def test_list_merged_users_pre_registered_only(
    app: web.Application,
    product_name: ProductName,
    mixed_user_data: MixedUserTestData,
):
    """Test pre-registered only user details are correctly returned."""
    asyncpg_engine = get_asyncpg_engine(app)

    users_list, _ = await _accounts_repository.list_merged_pre_and_registered_users(
        asyncpg_engine,
        product_name=product_name,
        filter_include_deleted=False,
    )

    pre_reg_only_user = next(
        (user for user in users_list if user["email"] == mixed_user_data.pre_reg_email),
        None,
    )

    assert pre_reg_only_user is not None, "Pre-registered user should be in results"
    assert pre_reg_only_user["is_pre_registered"] is True
    assert pre_reg_only_user["pre_reg_user_id"] is None
    assert pre_reg_only_user["user_id"] is None, "Pre-registered only user shouldn't have a user_id"
    assert pre_reg_only_user["institution"] == "Pre-Reg Institution"
    assert pre_reg_only_user["first_name"] == "Pre-Registered"
    assert pre_reg_only_user["last_name"] == "Only"
    assert pre_reg_only_user["created_by"] == mixed_user_data.created_by_user_id


async def test_list_merged_users_linked_user(
    app: web.Application,
    product_name: ProductName,
    mixed_user_data: MixedUserTestData,
):
    """Test that a linked user (both registered and pre-registered) has correct data."""
    asyncpg_engine = get_asyncpg_engine(app)

    users_list, _ = await _accounts_repository.list_merged_pre_and_registered_users(
        asyncpg_engine,
        product_name=product_name,
        filter_include_deleted=False,
    )

    product_owner = next(
        (user for user in users_list if user["email"] == mixed_user_data.product_owner_email),
        None,
    )

    assert product_owner is not None, "Product owner should be in results"
    assert product_owner["is_pre_registered"] is True, "Should prefer pre-registration record"
    assert product_owner["pre_reg_user_id"] == mixed_user_data.product_owner_id
    assert product_owner["user_id"] == mixed_user_data.product_owner_id, "Should be linked to existing user"
    assert product_owner["institution"] == "Owner Institution"
    assert product_owner["first_name"] == "Owner", "Should use pre-registration first name"
    assert product_owner["user_name"] is not None, "Should include user_name from users table"
    assert product_owner["status"] is not None, "Should include status from users table"
    assert product_owner["account_request_status"] == AccountRequestStatus.PENDING
    assert product_owner["created_by"] == mixed_user_data.created_by_user_id


async def test_list_merged_users_filter_pending(
    app: web.Application,
    product_name: ProductName,
    mixed_user_data: MixedUserTestData,
):
    """Test filtering by PENDING account request status."""
    asyncpg_engine = get_asyncpg_engine(app)

    pending_users, pending_count = await _accounts_repository.list_merged_pre_and_registered_users(
        asyncpg_engine,
        product_name=product_name,
        filter_any_account_request_status=[AccountRequestStatus.PENDING],
        filter_include_deleted=False,
    )

    assert pending_count == 2
    assert len(pending_users) == 2
    pending_emails = [user["email"] for user in pending_users]
    assert mixed_user_data.pre_reg_email in pending_emails
    assert mixed_user_data.product_owner_email in pending_emails
    assert mixed_user_data.approved_email not in pending_emails


async def test_list_merged_users_filter_approved(
    app: web.Application,
    product_name: ProductName,
    mixed_user_data: MixedUserTestData,
):
    """Test filtering by APPROVED account request status."""
    asyncpg_engine = get_asyncpg_engine(app)

    approved_users, approved_count = await _accounts_repository.list_merged_pre_and_registered_users(
        asyncpg_engine,
        product_name=product_name,
        filter_any_account_request_status=[AccountRequestStatus.APPROVED],
        filter_include_deleted=False,
    )

    assert approved_count == 1
    assert len(approved_users) == 1
    approved_emails = {user["email"] for user in approved_users}
    assert approved_emails == {mixed_user_data.approved_email}
    assert all(user["account_request_status"] == AccountRequestStatus.APPROVED for user in approved_users)


async def test_list_merged_users_multiple_statuses(
    app: web.Application,
    product_name: ProductName,
    mixed_user_data: MixedUserTestData,
):
    """Test filtering by multiple account request statuses."""
    asyncpg_engine = get_asyncpg_engine(app)

    mixed_status_users, mixed_status_count = await _accounts_repository.list_merged_pre_and_registered_users(
        asyncpg_engine,
        product_name=product_name,
        filter_any_account_request_status=[
            AccountRequestStatus.PENDING,
            AccountRequestStatus.APPROVED,
        ],
        filter_include_deleted=False,
    )

    assert mixed_status_count == 3
    assert len(mixed_status_users) == 3
    mixed_status_emails = [user["email"] for user in mixed_status_users]
    assert mixed_user_data.pre_reg_email in mixed_status_emails
    assert mixed_user_data.product_owner_email in mixed_status_emails
    assert mixed_user_data.approved_email in mixed_status_emails


@pytest.mark.parametrize(
    "filter_statuses,filter_registered,expected_present,expected_absent",
    [
        (
            [AccountRequestStatus.PENDING],
            True,
            ["product_owner_email"],
            ["pre_reg_email", "approved_email"],
        ),
        (
            [AccountRequestStatus.PENDING],
            False,
            ["pre_reg_email"],
            ["product_owner_email", "approved_email"],
        ),
        (
            [AccountRequestStatus.APPROVED],
            False,
            ["approved_email"],
            ["pre_reg_email", "product_owner_email"],
        ),
        (
            [AccountRequestStatus.APPROVED],
            True,
            [],
            ["pre_reg_email", "product_owner_email", "approved_email"],
        ),
    ],
)
async def test_list_merged_users_with_registered_filter(
    app: web.Application,
    product_name: ProductName,
    mixed_user_data: MixedUserTestData,
    filter_statuses: list[AccountRequestStatus],
    filter_registered: bool,
    expected_present: list[str],
    expected_absent: list[str],
):
    """Test account request status and registered filters in combination."""
    asyncpg_engine = get_asyncpg_engine(app)

    users_list, total_count = await _accounts_repository.list_merged_pre_and_registered_users(
        asyncpg_engine,
        product_name=product_name,
        filter_any_account_request_status=filter_statuses,
        filter_registered=filter_registered,
        filter_include_deleted=False,
        pagination_limit=100,
        pagination_offset=0,
    )

    assert total_count == len(users_list)

    found_emails = {user["email"] for user in users_list}

    for expected_attr in expected_present:
        assert getattr(mixed_user_data, expected_attr) in found_emails

    for expected_attr in expected_absent:
        assert getattr(mixed_user_data, expected_attr) not in found_emails

    assert all((user["user_id"] is not None) is filter_registered for user in users_list)


async def test_list_merged_users_pagination(
    app: web.Application,
    product_name: ProductName,
    mixed_user_data: MixedUserTestData,
):
    """Test pagination of merged user results."""
    asyncpg_engine = get_asyncpg_engine(app)

    page1_users, total_count = await _accounts_repository.list_merged_pre_and_registered_users(
        asyncpg_engine,
        product_name=product_name,
        filter_include_deleted=False,
        pagination_limit=2,
        pagination_offset=0,
    )

    page2_users, _ = await _accounts_repository.list_merged_pre_and_registered_users(
        asyncpg_engine,
        product_name=product_name,
        filter_include_deleted=False,
        pagination_limit=2,
        pagination_offset=2,
    )

    assert len(page1_users) == 2, "First page should have 2 users"
    assert total_count >= 3, "Total count should report all users"

    if total_count > 2:
        assert len(page2_users) > 0, "Second page should have at least 1 user"

    page1_emails = [user["email"] for user in page1_users]
    page2_emails = [user["email"] for user in page2_users]
    assert not set(page1_emails).intersection(set(page2_emails)), "Pages should have different users"
