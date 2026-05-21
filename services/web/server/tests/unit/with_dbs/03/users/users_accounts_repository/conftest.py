# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import AsyncIterator
from typing import Any

import pytest
import sqlalchemy as sa
from aiohttp import web
from common_library.users_enums import AccountRequestStatus
from models_library.products import ProductName
from pytest_simcore.helpers.webserver_users import MixedUserTestData, SortingUserTestData
from simcore_postgres_database.models.users_details import (
    users_pre_registration_details,
)
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.users import _accounts_repository


@pytest.fixture
async def pre_registration_details_db_cleanup(
    app: web.Application,
) -> AsyncIterator[list[int]]:
    """Fixture to clean up pre-registration details after tests.

    Returns a list that tests can append pre-registration IDs to.
    All records with these IDs will be deleted when the fixture is torn down.
    """
    pre_registration_ids = []
    yield pre_registration_ids

    if pre_registration_ids:
        asyncpg_engine = get_asyncpg_engine(app)
        async with asyncpg_engine.connect() as conn:
            await conn.execute(
                sa.delete(users_pre_registration_details).where(
                    users_pre_registration_details.c.id.in_(pre_registration_ids)
                )
            )
            await conn.commit()


@pytest.fixture
async def sorting_user_data(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
    pre_registration_details_db_cleanup: list[int],
) -> SortingUserTestData:
    asyncpg_engine = get_asyncpg_engine(app)
    created_by_user_id = product_owner_user["id"]

    users_to_create = [
        {
            "email": "zeta@example.com",
            "pre_first_name": "Alice",
            "pre_last_name": "Zephyr",
        },
        {
            "email": "alpha@example.com",
            "pre_first_name": "Zoe",
            "pre_last_name": "Alpha",
        },
        {
            "email": "middle@example.com",
            "pre_first_name": "Bob",
            "pre_last_name": "Middle",
        },
    ]

    for user_data in users_to_create:
        pre_registration_id = await _accounts_repository.create_user_pre_registration(
            asyncpg_engine,
            email=user_data["email"],
            created_by=created_by_user_id,
            product_name=product_name,
            pre_first_name=user_data["pre_first_name"],
            pre_last_name=user_data["pre_last_name"],
            institution="Sorting Institution",
        )
        pre_registration_details_db_cleanup.append(pre_registration_id)

    return SortingUserTestData(
        emails_by_name_asc=["zeta@example.com", "middle@example.com", "alpha@example.com"],
    )


@pytest.fixture
async def mixed_user_data(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
    pre_registration_details_db_cleanup: list[int],
) -> MixedUserTestData:
    """Create a mix of pre-registered users in different states to test listing functionality.

    Creates:
    1. A pre-registered only user (PENDING)
    2. A pre-registration for the existing product owner (linked and pending)
    3. A pre-registered user in APPROVED state
    """
    asyncpg_engine = get_asyncpg_engine(app)
    created_by_user_id = product_owner_user["id"]

    # 1. Create a pre-registered user that is not in the users table - PENDING status
    pre_reg_email = "pre.registered.only@example.com"
    pre_reg_id = await _accounts_repository.create_user_pre_registration(
        asyncpg_engine,
        email=pre_reg_email,
        created_by=created_by_user_id,
        product_name=product_name,
        pre_first_name="Pre-Registered",
        pre_last_name="Only",
        institution="Pre-Reg Institution",
        address="123 Pre Street",
        city="Pre City",
        state="Pre State",
        postal_code="12345",
        country="US",
    )
    pre_registration_details_db_cleanup.append(pre_reg_id)

    # 2. Create a pre-registration for the product_owner_user (both registered and pre-registered)
    owner_pre_reg_id = await _accounts_repository.create_user_pre_registration(
        asyncpg_engine,
        email=product_owner_user["email"],
        created_by=created_by_user_id,
        product_name=product_name,
        pre_first_name="Owner",
        pre_last_name="PreReg",
        institution="Owner Institution",
        link_to_existing_user=True,
    )
    pre_registration_details_db_cleanup.append(owner_pre_reg_id)

    # 3. Create another pre-registered user with APPROVED status
    approved_email = "approved.user@example.com"
    approved_reg_id = await _accounts_repository.create_user_pre_registration(
        asyncpg_engine,
        email=approved_email,
        created_by=created_by_user_id,
        product_name=product_name,
        pre_first_name="Approved",
        pre_last_name="User",
        institution="Approved Institution",
    )
    pre_registration_details_db_cleanup.append(approved_reg_id)

    await _accounts_repository.review_user_pre_registration(
        asyncpg_engine,
        pre_registration_id=approved_reg_id,
        reviewed_by=created_by_user_id,
        new_status=AccountRequestStatus.APPROVED,
    )

    return MixedUserTestData(
        created_by_user_id=created_by_user_id,
        product_owner_email=product_owner_user["email"],
        product_owner_id=product_owner_user["id"],
        pre_reg_email=pre_reg_email,
        pre_reg_id=pre_reg_id,
        owner_pre_reg_id=owner_pre_reg_id,
        approved_email=approved_email,
        approved_reg_id=approved_reg_id,
    )
