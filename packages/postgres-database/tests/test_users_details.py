# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import AsyncIterable
from dataclasses import dataclass
from typing import Any

import pytest
import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from common_library.groups_enums import GroupType
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


@pytest.fixture
async def product(
    faker: Faker,
    asyncpg_engine: AsyncEngine,
) -> AsyncIterable[dict[str, Any]]:
    async with insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup  # noqa: SIM117
        asyncpg_engine,
        table=groups,
        values=random_group(faker=faker, type=GroupType.STANDARD.name),
        pk_col=products.c.name,
    ) as product_group:
        async with insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
            asyncpg_engine,
            table=products,
            values=random_product(
                fake=faker, name="s4l", group_id=product_group["gid"]
            ),
            pk_col=products.c.name,
        ) as row:
            yield row


@pytest.fixture
async def po_user(
    faker: Faker,
    asyncpg_engine: AsyncEngine,
) -> AsyncIterable[dict[str, Any]]:
    async with insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
        asyncpg_engine,
        table=users,
        values=random_user(faker, role=UserRole.PRODUCT_OWNER),
        pk_col=users.c.id,
    ) as row:
        yield row


@pytest.mark.acceptance_test(
    "pre-registration in https://github.com/ITISFoundation/osparc-simcore/issues/5138"
)
async def test_user_creation_workflow(
    asyncpg_engine: AsyncEngine,
    faker: Faker,
    po_user: dict[str, Any],
    product: dict[str, Any],
):
    product_name = product["name"]

    # a PO creates an invitation
    fake_pre_registration_data = random_pre_registration_details(
        faker, created_by=po_user["id"], product_name=product_name
    )

    async with transaction_context(asyncpg_engine) as connection:
        pre_email = await connection.scalar(
            sa.insert(users_pre_registration_details)
            .values(**fake_pre_registration_data)
            .returning(users_pre_registration_details.c.pre_email)
        )
    assert pre_email is not None
    assert pre_email == fake_pre_registration_data["pre_email"]

    async with transaction_context(asyncpg_engine) as connection:
        # user gets created
        new_user = await UsersRepo.new_user(
            connection,
            email=pre_email,
            password_hash="123456",  # noqa: S106
            status=UserStatus.ACTIVE,
            expires_at=None,
        )
        await UsersRepo.link_and_update_user_from_pre_registration(
            connection, new_user_id=new_user.id, new_user_email=new_user.email
        )

    async with pass_or_acquire_connection(asyncpg_engine) as connection:
        invoice_data = await UsersRepo.get_billing_details(
            connection, user_id=new_user.id
        )
        assert invoice_data is not None

    # drafts converting data models from https://github.com/ITISFoundation/osparc-simcore/pull/5402
    @dataclass
    class UserAddress:
        line1: str | None
        state: str | None
        postal_code: str | None
        city: str | None
        country: str

        @classmethod
        def create_from_db(cls, row: RowProxy):
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

    user_address = UserAddress.create_from_db(invoice_data)

    # Expects something like
    # {
    #   "line1": "Jones, Jefferson and Rivera. 5938 Ramos Pike Suite 080, Lake Marytown, RI 65195",
    #   "state": "Virginia",
    #   "postal_code": "08756",
    #   "city": "Johnmouth",
    #   "country": "Trinidad and Tobago"
    # }

    assert user_address.line1
    assert user_address.state == fake_pre_registration_data["state"]
    assert user_address.postal_code == fake_pre_registration_data["postal_code"]
    assert user_address.country == fake_pre_registration_data["country"]

    # now let's update the user
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

    for _ in range(2):
        async with transaction_context(asyncpg_engine) as connection:
            await UsersRepo.link_and_update_user_from_pre_registration(
                connection, new_user_id=new_user.id, new_user_email=new_user.email
            )

            result = await connection.execute(
                users.select().where(users.c.id == new_user.id)
            )
            current_user = result.one()
            assert current_user

            # overriden!
            assert current_user.first_name != updated_user.first_name
