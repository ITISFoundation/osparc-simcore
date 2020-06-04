# pylint: disable=no-value-for-parameter
# TODO: reuse in auto and manual testing!

import asyncio
from uuid import uuid4

import aiopg.sa
import faker
import sqlalchemy as sa
import yaml

import simcore_service_api_gateway.db_models as orm
import simcore_postgres_database.cli as pg_cli

from typing import Dict
import os


DSN_FORMAT = "postgresql://{user}:{password}@{host}:{port}/{database}"

default_db_settings = dict(
    user=os.environ.get("POSTGRES_USER", "test"),
    password=os.environ.get("POSTGRES_PASSWORD", "test"),
    host=os.environ.get("POSTGRES_HOST", "localhost"),
    port=os.environ.get("POSTGRES_PORT", 5432),
    database=os.environ.get("POSTGRES_DB", 5432),
)
default_dsn = DSN_FORMAT.format(**default_db_settings)

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


def init_tables(dsn: str = default_dsn):
    engine = sa.create_engine(dsn)
    meta = orm.metadata
    meta.drop_all(engine)
    # meta.create_all(engine, tables=[orm.api_keys, orm.users])


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


async def fill_tables(dsn: str = default_dsn):
    async with aiopg.sa.create_engine(dsn) as engine:
        async with engine.acquire() as conn:
            uid: int = await conn.scalar(
                orm.users.insert().values(**random_user(name="me", email="me@bar.foo"))
            )

            await conn.scalar(
                orm.api_keys.insert().values(
                    **random_api_key(
                        display_name="test key",
                        user_id=uid,
                        api_key="key",
                        api_secret="secret",
                    )
                )
            )


async def main():

    # discover
    settings = pg_cli.discover.callback(**default_db_settings)
    dsn: str = DSN_FORMAT.format(**settings)

    # upgrade
    pg_cli.upgrade.callback("head")

    # FIXME: if already there, it will fail
    await fill_tables(dsn)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.stop()
