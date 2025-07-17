# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import AsyncIterable, AsyncIterator
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, Protocol, Self

import pytest
import sqlalchemy as sa
from common_library.groups_enums import GroupType
from common_library.users_enums import AccountRequestStatus
from faker import Faker
from pytest_simcore.helpers.faker_factories import (
    random_group,
    random_pre_registration_details,
    random_product,
    random_user,
)
from pytest_simcore.helpers.postgres_tools import (
    insert_and_get_row_lifespan,
)
from simcore_postgres_database.models.groups import groups
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import UserRole, UserStatus, users
from simcore_postgres_database.models.users_details import (
    users_pre_registration_details,
)
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from simcore_postgres_database.utils_users import UsersRepo
from sqlalchemy.ext.asyncio import AsyncEngine


class CreateProductCallable(Protocol):
    """Callable that creates a product and returns its row."""

    async def __call__(self, name: str) -> dict[str, Any]: ...


@pytest.fixture
async def product_factory(
    faker: Faker,
    asyncpg_engine: AsyncEngine,
) -> AsyncIterator[CreateProductCallable]:
    """Fixture that yields a factory function to create products.

    All products created with this factory will be automatically cleaned up when the test ends.
    """
    async with AsyncExitStack() as exit_stack:

        async def _create_product(name: str) -> dict[str, Any]:
            # 1. create a product group
            product_group_row = await exit_stack.enter_async_context(
                insert_and_get_row_lifespan(
                    asyncpg_engine,
                    table=groups,
                    values=random_group(fake=faker, type=GroupType.STANDARD.name),
                    pk_col=groups.c.gid,
                )
            )

            # 2. create the product using that group
            product_name = name or faker.pystr(min_chars=3, max_chars=10)
            return await exit_stack.enter_async_context(
                insert_and_get_row_lifespan(
                    asyncpg_engine,
                    table=products,
                    values=random_product(
                        fake=faker,
                        name=product_name,
                        group_id=int(product_group_row["gid"]),
                    ),
                    pk_col=products.c.name,
                )
            )

        yield _create_product


@pytest.fixture
async def product(product_factory: CreateProductCallable) -> dict[str, Any]:
    """Returns a single product for backward compatibility."""
    return await product_factory("s4l")


@pytest.fixture
async def product_owner_user(
    faker: Faker,
    asyncpg_engine: AsyncEngine,
) -> AsyncIterable[dict[str, Any]]:
    async with insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
        asyncpg_engine,
        table=users,
        values=random_user(
            faker,
            email="po-user@email.com",
            name="po-user-fixture",
            role=UserRole.PRODUCT_OWNER,
        ),
        pk_col=users.c.id,
    ) as row:
        yield row


@dataclass
class UserAddress:
    """Model for user address information from database records."""

    line1: str | None
    state: str | None
    postal_code: str | None
    city: str | None
    country: str

    @classmethod
    def create_from_db(cls, row) -> Self:
        parts = (
            getattr(row, col_name)
            for col_name in ("institution", "address")
            if getattr(row, col_name)
        )
        return cls(
            line1=". ".join(parts),
            state=row.state,
            postal_code=row.postal_code,
            city=row.city,
            country=row.country,
        )


@pytest.fixture
async def pre_registered_user(
    asyncpg_engine: AsyncEngine,
    faker: Faker,
    product_owner_user: dict[str, Any],
    product: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Creates a pre-registered user and returns the email and registration data."""
    product_name = product["name"]
    fake_pre_registration_data = random_pre_registration_details(
        faker,
        pre_email="pre-registered@user.com",
        created_by=product_owner_user["id"],
        product_name=product_name,
    )

    async with transaction_context(asyncpg_engine) as connection:
        pre_email = await connection.scalar(
            sa.insert(users_pre_registration_details)
            .values(**fake_pre_registration_data)
            .returning(users_pre_registration_details.c.pre_email)
        )

    assert pre_email == fake_pre_registration_data["pre_email"]
    return pre_email, fake_pre_registration_data


async def test_user_requests_account_and_is_approved(
    asyncpg_engine: AsyncEngine,
    faker: Faker,
    product_owner_user: dict[str, Any],
    product: dict[str, Any],
):
    product_name = product["name"]

    # 1. User request an account
    interested_user_email = "interested@user.com"

    async with transaction_context(asyncpg_engine) as connection:
        pre_email = await connection.scalar(
            sa.insert(users_pre_registration_details)
            .values(
                **random_pre_registration_details(
                    faker,
                    pre_email=interested_user_email,
                    product_name=product_name,
                )
            )
            .returning(users_pre_registration_details.c.pre_email)
        )
    assert pre_email is not None
    assert pre_email == interested_user_email

    # 2. PO approves the account request
    async with transaction_context(asyncpg_engine) as connection:
        await connection.execute(
            users_pre_registration_details.update()
            .where(users_pre_registration_details.c.pre_email == pre_email)
            .values(
                account_request_status=AccountRequestStatus.APPROVED,
                account_request_reviewed_by=product_owner_user["id"],
                account_request_reviewed_at=sa.func.now(),
            )
        )

    # 3. Verify approval was recorded
    async with pass_or_acquire_connection(asyncpg_engine) as connection:
        result = await connection.execute(
            sa.select(
                users_pre_registration_details.c.account_request_status,
                users_pre_registration_details.c.account_request_reviewed_by,
                users_pre_registration_details.c.account_request_reviewed_at,
            ).where(users_pre_registration_details.c.pre_email == pre_email)
        )
        approval_record = result.one()
        assert approval_record.account_request_status == AccountRequestStatus.APPROVED
        assert approval_record.account_request_reviewed_by == product_owner_user["id"]
        assert approval_record.account_request_reviewed_at is not None


@pytest.mark.acceptance_test(
    "pre-registration link creation in https://github.com/ITISFoundation/osparc-simcore/issues/5138"
)
async def test_create_pre_registration_link(
    asyncpg_engine: AsyncEngine,
    faker: Faker,
    product_owner_user: dict[str, Any],
    product: dict[str, Any],
):
    """Test that a PO can create a pre-registration link for a user."""
    product_name = product["name"]

    # PO creates a pre-registration and sends an email with the invitation link
    fake_pre_registration_data = random_pre_registration_details(
        faker,
        pre_email="interested@user.com",
        created_by=product_owner_user["id"],
        product_name=product_name,
    )

    async with transaction_context(asyncpg_engine) as connection:
        pre_email = await connection.scalar(
            sa.insert(users_pre_registration_details)
            .values(**fake_pre_registration_data)
            .returning(users_pre_registration_details.c.pre_email)
        )

    assert pre_email is not None
    assert pre_email == fake_pre_registration_data["pre_email"]


@pytest.mark.acceptance_test(
    "pre-registration user creation in https://github.com/ITISFoundation/osparc-simcore/issues/5138"
)
async def test_create_and_link_user_from_pre_registration(
    asyncpg_engine: AsyncEngine,
    pre_registered_user: tuple[str, dict[str, Any]],
):
    """Test that a user can be created from a pre-registration link and is linked properly."""
    pre_email, _ = pre_registered_user

    # Invitation link is clicked and the user is created and linked to the pre-registration
    async with transaction_context(asyncpg_engine) as connection:
        # user gets created
        new_user = await UsersRepo.new_user(
            asyncpg_engine,
            connection,
            email=pre_email,
            password_hash="123456",  # noqa: S106
            status=UserStatus.ACTIVE,
            expires_at=None,
        )
        await UsersRepo.link_and_update_user_from_pre_registration(
            connection, new_user_id=new_user.id, new_user_email=new_user.email
        )

    # Verify the user was created and linked
    async with pass_or_acquire_connection(asyncpg_engine) as connection:
        result = await connection.execute(
            sa.select(users_pre_registration_details.c.user_id).where(
                users_pre_registration_details.c.pre_email == pre_email
            )
        )
        user_id = result.scalar()
        assert user_id == new_user.id


@pytest.mark.acceptance_test(
    "pre-registration billing info in https://github.com/ITISFoundation/osparc-simcore/issues/5138"
)
async def test_get_billing_details_from_pre_registration(
    asyncpg_engine: AsyncEngine,
    pre_registered_user: tuple[str, dict[str, Any]],
):
    """Test that billing details can be retrieved from pre-registration data."""
    pre_email, fake_pre_registration_data = pre_registered_user

    # Create the user
    async with transaction_context(asyncpg_engine) as connection:
        new_user = await UsersRepo.new_user(
            asyncpg_engine,
            connection,
            email=pre_email,
            password_hash="123456",  # noqa: S106
            status=UserStatus.ACTIVE,
            expires_at=None,
        )
        await UsersRepo.link_and_update_user_from_pre_registration(
            connection, new_user_id=new_user.id, new_user_email=new_user.email
        )

    # Get billing details
    async with pass_or_acquire_connection(asyncpg_engine) as connection:
        invoice_data = await UsersRepo.get_billing_details(
            connection, user_id=new_user.id
        )
        assert invoice_data is not None

    # Test UserAddress model conversion
    user_address = UserAddress.create_from_db(invoice_data)

    # Verify address fields match the pre-registration data
    assert user_address.line1
    assert user_address.state == fake_pre_registration_data["state"]
    assert user_address.postal_code == fake_pre_registration_data["postal_code"]
    assert user_address.country == fake_pre_registration_data["country"]


@pytest.mark.acceptance_test(
    "pre-registration user update in https://github.com/ITISFoundation/osparc-simcore/issues/5138"
)
async def test_update_user_from_pre_registration(
    asyncpg_engine: AsyncEngine,
    pre_registered_user: tuple[str, dict[str, Any]],
):
    """Test that pre-registration details override manual updates when re-linking."""
    pre_email, _ = pre_registered_user

    # Create the user and link to pre-registration
    async with transaction_context(asyncpg_engine) as connection:
        new_user = await UsersRepo.new_user(
            asyncpg_engine,
            connection,
            email=pre_email,
            password_hash="123456",  # noqa: S106
            status=UserStatus.ACTIVE,
            expires_at=None,
        )
        await UsersRepo.link_and_update_user_from_pre_registration(
            connection, new_user_id=new_user.id, new_user_email=new_user.email
        )

    # Update the user manually
    async with transaction_context(asyncpg_engine) as connection:
        result = await connection.execute(
            users.update()
            .values(first_name="My New Name")
            .where(users.c.id == new_user.id)
            .returning("*")
        )
        updated_user = result.one()

    assert updated_user
    assert updated_user.first_name == "My New Name"
    assert updated_user.id == new_user.id

    # Re-link the user to pre-registration, which should override manual updates
    async with transaction_context(asyncpg_engine) as connection:
        await UsersRepo.link_and_update_user_from_pre_registration(
            connection, new_user_id=new_user.id, new_user_email=new_user.email
        )

        result = await connection.execute(
            users.select().where(users.c.id == new_user.id)
        )
        current_user = result.one()
        assert current_user

        # Verify that the manual updates were overridden
        assert current_user.first_name != updated_user.first_name


async def test_user_preregisters_for_multiple_products_with_different_outcomes(
    asyncpg_engine: AsyncEngine,
    faker: Faker,
    product_owner_user: dict[str, Any],
    product_factory: CreateProductCallable,
):
    """Test scenario where a user pre-registers for multiple products and gets different approval outcomes."""
    # Create two products
    product1 = await product_factory("s4l")
    product2 = await product_factory("tip")

    # User email for pre-registration
    user_email = "multi-product-user@example.com"

    # User pre-registers for both products
    async with transaction_context(asyncpg_engine) as connection:
        # Pre-register for product1
        await connection.execute(
            sa.insert(users_pre_registration_details).values(
                **random_pre_registration_details(
                    faker,
                    pre_email=user_email,
                    product_name=product1["name"],
                )
            )
        )

        # Pre-register for product2
        await connection.execute(
            sa.insert(users_pre_registration_details).values(
                **random_pre_registration_details(
                    faker,
                    pre_email=user_email,
                    product_name=product2["name"],
                )
            )
        )

    # Verify both pre-registrations were created
    async with pass_or_acquire_connection(asyncpg_engine) as connection:
        result = await connection.execute(
            sa.select(
                users_pre_registration_details.c.pre_email,
                users_pre_registration_details.c.product_name,
                users_pre_registration_details.c.account_request_status,
            )
            .where(users_pre_registration_details.c.pre_email == user_email)
            .order_by(users_pre_registration_details.c.product_name)
        )

        registrations = result.fetchall()
        assert len(registrations) == 2
        assert all(
            reg.account_request_status == AccountRequestStatus.PENDING
            for reg in registrations
        )

    # 2. PO approves and rejects the requests
    async with transaction_context(asyncpg_engine) as connection:
        # PO approves the request for product1
        await connection.execute(
            users_pre_registration_details.update()
            .where(
                (users_pre_registration_details.c.pre_email == user_email)
                & (users_pre_registration_details.c.product_name == product1["name"])
            )
            .values(
                account_request_status=AccountRequestStatus.APPROVED,
                account_request_reviewed_by=product_owner_user["id"],
                account_request_reviewed_at=sa.func.now(),
            )
        )

        # PO rejects the request for product2
        await connection.execute(
            users_pre_registration_details.update()
            .where(
                (users_pre_registration_details.c.pre_email == user_email)
                & (users_pre_registration_details.c.product_name == product2["name"])
            )
            .values(
                account_request_status=AccountRequestStatus.REJECTED,
                account_request_reviewed_by=product_owner_user["id"],
                account_request_reviewed_at=sa.func.now(),
            )
        )

    # Verify the status updates
    async with pass_or_acquire_connection(asyncpg_engine) as connection:
        result = await connection.execute(
            sa.select(
                users_pre_registration_details.c.product_name,
                users_pre_registration_details.c.account_request_status,
                users_pre_registration_details.c.account_request_reviewed_by,
                users_pre_registration_details.c.account_request_reviewed_at,
            )
            .where(users_pre_registration_details.c.pre_email == user_email)
            .order_by(users_pre_registration_details.c.created)
        )

        registrations = result.fetchall()
        assert len(registrations) == 2

        # Check product1 was approved
        assert registrations[0].product_name == product1["name"]
        assert registrations[0].account_request_status == AccountRequestStatus.APPROVED
        assert registrations[0].account_request_reviewed_by == product_owner_user["id"]
        assert registrations[0].account_request_reviewed_at is not None

        # Check product2 was rejected
        assert registrations[1].product_name == product2["name"]
        assert registrations[1].account_request_status == AccountRequestStatus.REJECTED
        assert registrations[1].account_request_reviewed_by == product_owner_user["id"]
        assert registrations[1].account_request_reviewed_at is not None

    # 3.Now create a user account with the approved pre-registration
    async with transaction_context(asyncpg_engine) as connection:
        new_user = await UsersRepo.new_user(
            asyncpg_engine,
            connection,
            email=user_email,
            password_hash="123456",  # noqa: S106
            status=UserStatus.ACTIVE,
            expires_at=None,
        )
        await UsersRepo.link_and_update_user_from_pre_registration(
            connection, new_user_id=new_user.id, new_user_email=new_user.email
        )

    # Verify both pre-registrations are linked to the new user
    async with pass_or_acquire_connection(asyncpg_engine) as connection:
        result = await connection.execute(
            sa.select(
                users_pre_registration_details.c.product_name,
                users_pre_registration_details.c.account_request_status,
                users_pre_registration_details.c.user_id,
            )
            .where(users_pre_registration_details.c.pre_email == user_email)
            .order_by(users_pre_registration_details.c.product_name)
        )

        registrations = result.fetchall()
        assert len(registrations) == 2

        # Both registrations should be linked to the same user, regardless of approval status
        assert all(reg.user_id == new_user.id for reg in registrations)
