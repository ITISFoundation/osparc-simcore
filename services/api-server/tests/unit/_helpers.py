from pprint import pformat
from typing import Dict

import faker

# import sqlalchemy as sa
# from aiopg.sa.result import ResultProxy
from aiopg.sa.result import RowProxy

import passlib.hash
import simcore_service_api_server.db.tables as orm
from simcore_service_api_server.db.repositories.api_keys import ApiKeyInDB
from simcore_service_api_server.db.repositories.base import BaseRepository
from simcore_service_api_server.db.repositories.users import UsersRepository

fake = faker.Faker()


def _hash_it(password: str) -> str:
    return passlib.hash.sha256_crypt.using(rounds=1000).hash(password)


# TODO: this should be generated from the metadata in orm.users table
def random_user(**overrides) -> Dict:
    data = dict(
        name=fake.name(),
        email=fake.email(),
        password_hash=_hash_it("secret"),
        status=orm.UserStatus.ACTIVE,
        created_ip=fake.ipv4(),
    )

    password = overrides.pop("password")
    if password:
        overrides["password_hash"] = _hash_it(password)

    data.update(overrides)
    return data


class RWUsersRepository(UsersRepository):
    # pylint: disable=no-value-for-parameter

    async def create(self, **user) -> int:
        values = random_user(**user)
        user_id = await self.connection.scalar(orm.users.insert().values(**values))

        print("Created user ", pformat(values), f"with user_id={user_id}")
        return user_id


class RWApiKeysRepository(BaseRepository):
    # pylint: disable=no-value-for-parameter

    async def create(self, name: str, *, api_key: str, api_secret: str, user_id: int):
        values = dict(
            display_name=name, user_id=user_id, api_key=api_key, api_secret=api_secret,
        )
        _id = await self.connection.scalar(orm.api_keys.insert().values(**values))

        # check inserted
        row: RowProxy = await (
            await self.connection.execute(
                orm.api_keys.select().where(orm.api_keys.c.id == _id)
            )
        ).first()

        return ApiKeyInDB.from_orm(row)
