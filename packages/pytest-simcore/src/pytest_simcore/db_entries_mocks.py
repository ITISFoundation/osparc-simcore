from typing import Any, Callable, Dict, Iterator

import pytest
import sqlalchemy as sa
from faker import Faker
from simcore_postgres_database.models.users import UserRole, UserStatus, users


@pytest.fixture()
def registered_user(
    postgres_db: sa.engine.Engine, faker: Faker
) -> Iterator[Callable[..., Dict]]:
    created_user_ids = []

    def creator(**user_kwargs) -> Dict[str, Any]:
        with postgres_db.connect() as con:
            # removes all users before continuing
            user_config = {
                "id": len(created_user_ids) + 1,
                "name": faker.name(),
                "email": faker.email(),
                "password_hash": faker.password(),
                "status": UserStatus.ACTIVE,
                "role": UserRole.USER,
            }
            user_config.update(user_kwargs)

            con.execute(
                users.insert().values(user_config).returning(sa.literal_column("*"))
            )
            # this is needed to get the primary_gid correctly
            result = con.execute(
                sa.select([users]).where(users.c.id == user_config["id"])
            )
            user = result.first()
            assert user
            created_user_ids.append(user["id"])
        return dict(user)

    yield creator

    with postgres_db.connect() as con:
        con.execute(users.delete().where(users.c.id.in_(created_user_ids)))
