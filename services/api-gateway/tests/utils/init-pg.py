# pylint: disable=no-value-for-parameter
# TODO: reuse in auto and manual testing!

import asyncio
from uuid import uuid4

import aiopg.sa
import faker
import sqlalchemy as sa
import yaml

import simcore_service_api_gateway.db_models as orm

from typing import Dict

DSN = "postgresql://{user}:{password}@{host}:{port}/{database}".format(
    user="test", password="test", host="localhost", port=5432, database="test",
)


fake = faker.Faker()


def load_db_config() -> Dict:
    # TODO:
    with open("docker-compose-resolved.yaml") as fh:
        config = yaml.safe_load(fh)
    environ = config["services"]["postgres"]["environment"]

    return dict(
        user=environ["POSTGRES_USER"],
        password=environ["POSTGRES_PASSWORD"],
        host="localhost",
        port=5432,
        database=environ["POSTGRES_DB"],
    )


def init_tables():
    engine = sa.create_engine(DSN)
    meta = orm.metadata
    meta.drop_all(engine)
    meta.create_all(engine, tables=[orm.api_keys, orm.users])


def random_user(**overrides):
    data = dict(
        name=fake.name(),
        email=fake.email(),
        password_hash=fake.numerify(text="#" * 5),
        status=orm.UserStatus.ACTIVE,
        created_ip=fake.ipv4(),
    )
    data.update(overrides)
    return data


def random_api_key(**overrides):
    data = dict(
        user_id=1, display_name=fake.word(), api_key=uuid4(), api_secret=uuid4(),
    )
    data.update(overrides)
    return data


async def fill_tables():
    async with aiopg.sa.create_engine(DSN) as engine:
        async with engine.acquire() as conn:
            uid: int = await conn.scalar(
                orm.users.insert().values(**random_user(name="me", email="me@bar.foo"))
            )

            await conn.scalar(
                orm.api_keys.insert().values(
                    **random_api_key(display_name="test key", user_id=uid)
                )
            )


def main():
    init_tables()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(fill_tables())
    loop.stop()


if __name__ == "__main__":
    main()
