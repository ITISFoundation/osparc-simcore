from simcore_postgres_database.models.users import users
from simcore_postgres_database.models.users_secrets import users_secrets

from .faker_factories import random_user, random_user_secrets

# from .postgres_tools import insert_and_get_row_lifespan


async def insert_user_and_secrets(conn, **overrides) -> int:
    password = overrides.pop("password", None)
    # user data
    user_id = await conn.scalar(
        users.insert().values(**random_user(**overrides)).returning(users.c.id)
    )
    assert user_id is not None

    # secrets
    await conn.execute(
        users_secrets.insert().values(
            **random_user_secrets(user_id=user_id, password=password)
        )
    )

    return user_id


# async def insert_and_get_user_lifespan(sqlalchemy_async_engine: AsyncEngine, **overrides):

#     password = overrides.pop("password")

#     exit_stack =  contextlib.AsyncExitStack()

#     exit_stack(

#     insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
#         sqlalchemy_async_engine,
#         table=users,
#         values=random_user(**random_user(**overrides)),
#         pk_col=users.c.id,
#     )

#     await maybe_await(
#         conn.execute(
#             users_secrets.insert()
#             .values(**random_user_secrets(user_id=user_id, password=password))
#             .returning(users.c.id)
#         )
#     )


#     user = await exit_stack.enter_async_context(
#         insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
#             sqlalchemy_async_engine,
#             table=users_table,
#             values=random_user(**data),
#             pk_col=users_table.c.id,
#         )
#     )
