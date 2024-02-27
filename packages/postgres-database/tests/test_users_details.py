# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from faker import Faker
from pytest_simcore.helpers.rawdata_fakers import random_user
from simcore_postgres_database.models.users import UserRole, UserStatus, users
from simcore_postgres_database.models.users_details import invited_users
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


async def test_invited_user(connection: SAConnection, faker: Faker, po_user: RowProxy):

    # a PO creates an invitation
    fake_invitation = {
        "first_name": faker.first_name(),
        "last_name": faker.last_name(),
        "email": faker.email(),  # mandatory
        "company_name": faker.company(),
        "address": faker.address().replace("\n", ", "),
        "city": faker.city(),
        "state": faker.state(),
        "country": faker.country(),
        "postal_code": faker.postcode(),
        "created_by": po_user.id,
    }

    email = await connection.scalar(
        sa.insert(invited_users)
        .values(**fake_invitation)
        .returning(invited_users.c.email)
    )
    assert email is not None
    assert email == fake_invitation["email"]

    # user gets created
    new_user = await UsersRepo.new_user(
        connection,
        email=email,
        password_hash="123456",  # noqa: S106
        status=UserStatus.ACTIVE,
        expires_at=None,
    )
    await UsersRepo.update_details(connection, new_user)

    invoice_data = await UsersRepo.get_billing_details(connection, user_id=new_user.id)
    assert invoice_data is not None

    assert dict(invoice_data) == {key: fake_invitation.get(key) for key in invoice_data}
