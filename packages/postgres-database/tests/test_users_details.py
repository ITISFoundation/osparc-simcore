# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from dataclasses import dataclass

import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from faker import Faker
from pytest_simcore.helpers.faker_factories import (
    random_pre_registration_details,
    random_user,
)
from simcore_postgres_database.models.users import UserRole, UserStatus, users
from simcore_postgres_database.models.users_details import (
    users_pre_registration_details,
)
from simcore_postgres_database.utils_users import UsersRepo


@pytest.fixture
async def po_user(
    faker: Faker,
    connection: SAConnection,
):
    user_id = await connection.scalar(
        users.insert()
        .values(**random_user(faker, role=UserRole.PRODUCT_OWNER))
        .returning(users.c.id)
    )
    assert user_id

    result = await connection.execute(sa.select(users).where(users.c.id == user_id))
    yield await result.first()

    users.delete().where(users.c.id == user_id)


@pytest.mark.acceptance_test(
    "pre-registration in https://github.com/ITISFoundation/osparc-simcore/issues/5138"
)
async def test_user_creation_workflow(
    connection: SAConnection, faker: Faker, po_user: RowProxy
):
    # a PO creates an invitation
    fake_pre_registration_data = random_pre_registration_details(
        faker, created_by=po_user.id
    )

    pre_email = await connection.scalar(
        sa.insert(users_pre_registration_details)
        .values(**fake_pre_registration_data)
        .returning(users_pre_registration_details.c.pre_email)
    )
    assert pre_email is not None
    assert pre_email == fake_pre_registration_data["pre_email"]

    # user gets created
    new_user = await UsersRepo.new_user(
        connection,
        email=pre_email,
        password_hash="123456",  # noqa: S106
        status=UserStatus.ACTIVE,
        expires_at=None,
    )
    await UsersRepo.join_and_update_from_pre_registration_details(
        connection, new_user.id, new_user.email
    )

    invoice_data = await UsersRepo.get_billing_details(connection, user_id=new_user.id)
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
            parts = (row[c] for c in ("institution", "address") if row[c])
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
    result = await connection.execute(
        users.update()
        .values(first_name="My New Name")
        .where(users.c.id == new_user.id)
        .returning("*")
    )
    updated_user = await result.fetchone()

    assert updated_user
    assert updated_user.first_name == "My New Name"
    assert updated_user.id == new_user.id

    for _ in range(2):
        await UsersRepo.join_and_update_from_pre_registration_details(
            connection, new_user.id, new_user.email
        )

        result = await connection.execute(
            users.select().where(users.c.id == new_user.id)
        )
        current_user = await result.fetchone()
        assert current_user

        # overriden!
        assert current_user.first_name != updated_user.first_name
