from common_library.async_tools import maybe_await
from simcore_postgres_database.models.users import users
from simcore_postgres_database.models.users_secrets import users_secrets

from .faker_factories import random_user, random_user_secrets


async def insert_user_and_secrets(conn, **overrides) -> int:
    password = overrides.pop("password")
    # user data
    user_id = await maybe_await(
        conn.scalar(
            users.insert().values(**random_user(**overrides)).returning(users.c.id)
        )
    )
    assert user_id is not None

    # secrets
    await maybe_await(
        conn.execute(
            users_secrets.insert()
            .values(**random_user_secrets(user_id=user_id, password=password))
            .returning(users.c.id)
        )
    )

    return user_id
