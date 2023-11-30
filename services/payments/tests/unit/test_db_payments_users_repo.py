# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from models_library.basic_types import IDStr
from models_library.users import GroupID, UserID
from pydantic import EmailStr
from pytest_simcore.helpers.rawdata_fakers import random_user
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_postgres_database.models.users import users
from simcore_service_payments.db.payment_users_repo import PaymentsUsersRepo
from simcore_service_payments.services.postgres import get_engine

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    postgres_env_vars_dict: EnvVarsDict,
    with_disabled_rabbitmq_and_rpc: None,
    wait_for_postgres_ready_and_db_migrated: None,
):
    # set environs
    monkeypatch.delenv("PAYMENTS_POSTGRES", raising=False)

    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            **postgres_env_vars_dict,
            "POSTGRES_CLIENT_NAME": "payments-service-pg-client",
        },
    )


@pytest.fixture
async def user(
    app: FastAPI,
    user_email: EmailStr,
    user_name: IDStr,
    user_id: UserID,
):
    async with get_engine(app).begin() as conn:
        result = await conn.execute(
            users.insert()
            .values(
                **random_user(email=user_email, name=user_name),
                id=user_id,
            )
            .returning(users.c.id)
        )
        row = result.first()
        assert row
        # NOTE: groupid is triggered afterwards
        result = await conn.execute(sa.select(users).where(users.c.id == row.id))
        row = result.first()

    assert row
    yield row

    async with get_engine(app).begin() as conn:
        await conn.execute(users.delete().where(users.c.id == row.id))


@pytest.fixture
def user_primary_gid(user) -> GroupID:
    return user.primary_gid


async def test_payments_user_repo(
    app: FastAPI, user_id: UserID, user_primary_gid: GroupID
):
    repo = PaymentsUsersRepo(get_engine(app))
    assert await repo.get_primary_group_id(user_id) == user_primary_gid
