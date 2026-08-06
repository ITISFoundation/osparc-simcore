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
from simcore_postgres_database.models.groups import GroupType, groups, user_to_groups
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users_details import (
    users_pre_registration_details,
)
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.users import _accounts_repository


async def test_create_user_pre_registration(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
    pre_registration_details_db_cleanup: list[int],
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
    pre_registration_id = await _accounts_repository.create_user_pre_registration(
        asyncpg_engine,
        email=test_email,
        created_by=created_by_user_id,
        product_name=product_name,
        **pre_registration_details,
    )

    # Add to cleanup list
    pre_registration_details_db_cleanup.append(pre_registration_id)

    # Assert
    async with asyncpg_engine.connect() as conn:
        result = await conn.execute(
            sa.select(users_pre_registration_details).where(
                (users_pre_registration_details.c.pre_email == test_email)
                & (users_pre_registration_details.c.product_name == product_name)
            )
        )
        record = result.first()

    assert record is not None
    assert record.pre_email == test_email
    assert record.created_by == created_by_user_id
    assert record.product_name == product_name
    assert record.institution == institution


async def test_review_user_pre_registration(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
    pre_registration_details_db_cleanup: list[int],
):
    # Arrange
    asyncpg_engine = get_asyncpg_engine(app)

    test_email = "review.test@example.com"
    created_by_user_id = product_owner_user["id"]
    reviewer_id = product_owner_user["id"]
    institution = "Test Institution"
    pre_registration_details: dict[str, Any] = {
        "institution": institution,
        "pre_first_name": "Review",
        "pre_last_name": "Test",
    }

    pre_registration_id = await _accounts_repository.create_user_pre_registration(
        asyncpg_engine,
        email=test_email,
        created_by=created_by_user_id,
        product_name=product_name,
        **pre_registration_details,
    )
    pre_registration_details_db_cleanup.append(pre_registration_id)

    # Act
    new_status = AccountRequestStatus.APPROVED
    await _accounts_repository.review_user_pre_registration(
        asyncpg_engine,
        pre_registration_id=pre_registration_id,
        reviewed_by=reviewer_id,
        new_status=new_status,
    )

    # Assert
    registrations, count = await _accounts_repository.list_user_pre_registrations(
        asyncpg_engine,
        filter_by_pre_email=test_email,
        filter_by_product_name=product_name,
    )

    assert count == 1
    assert len(registrations) == 1

    reg = registrations[0]
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


async def test_review_user_pre_registration_with_invitation_extras(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
    pre_registration_details_db_cleanup: list[int],
):
    asyncpg_engine = get_asyncpg_engine(app)

    test_email = "review.with.invitation@example.com"
    created_by_user_id = product_owner_user["id"]
    reviewer_id = product_owner_user["id"]
    institution = "Test Institution"
    pre_registration_details: dict[str, Any] = {
        "institution": institution,
        "pre_first_name": "Review",
        "pre_last_name": "WithInvitation",
    }

    pre_registration_id = await _accounts_repository.create_user_pre_registration(
        asyncpg_engine,
        email=test_email,
        created_by=created_by_user_id,
        product_name=product_name,
        **pre_registration_details,
    )
    pre_registration_details_db_cleanup.append(pre_registration_id)

    invitation_extras = {
        "invitation": {
            "issuer": str(reviewer_id),
            "guest": test_email,
            "trial_account_days": 30,
            "extra_credits_in_usd": 100.0,
            "product_name": product_name,
            "created": "2024-01-01T00:00:00Z",
        }
    }

    new_status = AccountRequestStatus.APPROVED
    await _accounts_repository.review_user_pre_registration(
        asyncpg_engine,
        pre_registration_id=pre_registration_id,
        reviewed_by=reviewer_id,
        new_status=new_status,
        invitation_extras=invitation_extras,
    )

    registrations, count = await _accounts_repository.list_user_pre_registrations(
        asyncpg_engine,
        filter_by_pre_email=test_email,
        filter_by_product_name=product_name,
    )

    assert count == 1
    assert len(registrations) == 1

    reg = registrations[0]
    assert reg["id"] == pre_registration_id
    assert reg["pre_email"] == test_email
    assert reg["pre_first_name"] == "Review"
    assert reg["pre_last_name"] == "WithInvitation"
    assert reg["institution"] == institution
    assert reg["product_name"] == product_name
    assert reg["account_request_status"] == new_status
    assert reg["created_by"] == created_by_user_id
    assert reg["account_request_reviewed_by"] == reviewer_id
    assert reg["account_request_reviewed_at"] is not None

    assert reg["extras"] is not None
    assert "invitation" in reg["extras"]
    invitation_data = reg["extras"]["invitation"]
    assert invitation_data["issuer"] == str(reviewer_id)
    assert invitation_data["guest"] == test_email
    assert invitation_data["trial_account_days"] == 30
    assert invitation_data["extra_credits_in_usd"] == 100.0
    assert invitation_data["product_name"] == product_name


@pytest.mark.parametrize("link_to_existing_user,expected_linked", [(True, True), (False, False)])
async def test_create_pre_registration_with_existing_user_linking(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
    link_to_existing_user: bool,
    expected_linked: bool,
    pre_registration_details_db_cleanup: list[int],
):
    """Test that creating a pre-registration for an existing user correctly handles auto-linking."""
    asyncpg_engine = get_asyncpg_engine(app)
    existing_user_id = product_owner_user["id"]
    existing_user_email = product_owner_user["email"]

    pre_registration_id = await _accounts_repository.create_user_pre_registration(
        asyncpg_engine,
        email=existing_user_email,
        created_by=existing_user_id,
        product_name=product_name,
        link_to_existing_user=link_to_existing_user,
        pre_first_name="Link-Test",
        pre_last_name="User",
        institution=f"{'Auto-linked' if link_to_existing_user else 'No-link'} Institution",
    )
    pre_registration_details_db_cleanup.append(pre_registration_id)

    registrations, count = await _accounts_repository.list_user_pre_registrations(
        asyncpg_engine,
        filter_by_pre_email=existing_user_email,
        filter_by_product_name=product_name,
    )

    assert count == 1
    assert len(registrations) == 1

    reg = registrations[0]
    assert reg["id"] == pre_registration_id
    assert reg["pre_email"] == existing_user_email

    if expected_linked:
        assert reg["user_id"] == existing_user_id, "Should be linked to the existing user"
        assert reg["account_request_status"] == AccountRequestStatus.PENDING
        assert reg["account_request_reviewed_by"] is None
        assert reg["account_request_reviewed_at"] is None
    else:
        assert reg["user_id"] is None, "Should NOT be linked to any user"
        assert reg["account_request_status"] == AccountRequestStatus.PENDING
        assert reg["account_request_reviewed_by"] is None
        assert reg["account_request_reviewed_at"] is None


async def test_create_pre_registration_auto_approves_if_existing_user_in_requested_product(
    app: web.Application,
    product_name: ProductName,
    product_owner_user: dict[str, Any],
    pre_registration_details_db_cleanup: list[int],
):
    """Test that linked existing users are auto-approved only when already in the requested product group."""
    asyncpg_engine = get_asyncpg_engine(app)
    existing_user_id = product_owner_user["id"]
    existing_user_email = product_owner_user["email"]

    async with asyncpg_engine.begin() as conn:
        product_group_id = await conn.scalar(sa.select(products.c.group_id).where(products.c.name == product_name))
        if product_group_id is None:
            product_group_id = await conn.scalar(
                sa.insert(groups)
                .values(
                    name=f"product-group-{product_name}-{existing_user_id}",
                    description=f"Product group for {product_name}",
                    type=GroupType.STANDARD,
                )
                .returning(groups.c.gid)
            )
            assert product_group_id is not None
            await conn.execute(
                sa.update(products).where(products.c.name == product_name).values(group_id=product_group_id)
            )

        user_in_group = await conn.scalar(
            sa.select(user_to_groups.c.uid).where(
                (user_to_groups.c.uid == existing_user_id) & (user_to_groups.c.gid == product_group_id)
            )
        )
        if user_in_group is None:
            await conn.execute(sa.insert(user_to_groups).values(uid=existing_user_id, gid=product_group_id))

    pre_registration_id = await _accounts_repository.create_user_pre_registration(
        asyncpg_engine,
        email=existing_user_email,
        created_by=existing_user_id,
        product_name=product_name,
        link_to_existing_user=True,
        pre_first_name="Product",
        pre_last_name="Member",
    )
    pre_registration_details_db_cleanup.append(pre_registration_id)

    registrations, count = await _accounts_repository.list_user_pre_registrations(
        asyncpg_engine,
        filter_by_pre_email=existing_user_email,
        filter_by_product_name=product_name,
    )

    assert count == 1
    assert len(registrations) == 1
    reg = registrations[0]
    assert reg["id"] == pre_registration_id
    assert reg["user_id"] == existing_user_id
    assert reg["account_request_status"] == AccountRequestStatus.APPROVED
    assert reg["account_request_reviewed_by"] == existing_user_id
    assert reg["account_request_reviewed_at"] is not None
