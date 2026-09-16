# pylint: disable=redefined-outer-name

import uuid
from collections.abc import Iterator

import docker
import pytest
import sqlalchemy as sa
import tenacity
from pytest_simcore.helpers.postgres_tools import (
    PostgresTestConfig,
    cloned_pg_database_context,
    database_exists,
    drop_pg_template,
    migrated_pg_template_context,
)
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

postgres_config = {
    "user": "test",
    "password": "test",
    "database": "test",
    "host": "127.0.0.1",
}


@pytest.fixture(scope="module")
def postgres_container() -> Iterator[PostgresTestConfig]:
    client = docker.from_env()
    container = client.containers.run(
        "postgres:14.23",
        environment={
            "POSTGRES_USER": postgres_config["user"],
            "POSTGRES_PASSWORD": postgres_config["password"],
            "POSTGRES_DB": postgres_config["database"],
        },
        ports={"5432/tcp": None},  # random host port
        detach=True,
        auto_remove=False,
    )
    try:
        container.reload()
        bindings = container.attrs["NetworkSettings"]["Ports"]["5432/tcp"]
        port = str(bindings[0]["HostPort"])

        dsn = f"postgresql+psycopg2://{postgres_config['user']}:{postgres_config['password']}@{postgres_config['host']}:{port}/{postgres_config['database']}"
        engine = sa.create_engine(dsn)
        for attempt in tenacity.Retrying(wait=wait_fixed(0.2), stop=stop_after_delay(60), reraise=True):
            with attempt, engine.connect():
                pass
        engine.dispose()
        yield {**postgres_config, "port": port}
    finally:
        container.remove(force=True)
        client.close()


def _maintenance_engine(config: PostgresTestConfig) -> sa.engine.Engine:
    cfg = {**config, "database": "postgres"}
    return sa.create_engine(
        f"postgresql+psycopg2://{cfg['user']}:{cfg['password']}@{cfg['host']}:{cfg['port']}/{cfg['database']}",
        isolation_level="AUTOCOMMIT",
    )


def _engine_to(config: PostgresTestConfig, database: str) -> sa.engine.Engine:
    cfg = {**config, "database": database}
    return sa.create_engine(
        f"postgresql+psycopg2://{cfg['user']}:{cfg['password']}@{cfg['host']}:{cfg['port']}/{cfg['database']}"
    )


def _count_rows(engine: sa.engine.Engine, table: sa.Table) -> int:
    with engine.connect() as conn:
        return int(conn.execute(sa.select(sa.func.count()).select_from(table)).scalar())


def test_template_is_built_once_and_clones_are_isolated(postgres_container: PostgresTestConfig):
    """the template is migrated once and each clone starts from a pristine copy"""
    template_name = f"tpl_{uuid.uuid4().hex}"
    probe = sa.Table(
        "templates_probe",
        sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True),
    )

    with migrated_pg_template_context(postgres_container, template_name):
        # seed the schema into the template itself so clones inherit it
        template_engine = _engine_to(postgres_container, template_name)
        probe.metadata.create_all(template_engine, tables=[probe])
        template_engine.dispose()

        # clone 1: write data, must not leak to clone 2
        with cloned_pg_database_context(postgres_container, template_name) as engine1:
            with engine1.begin() as conn:
                conn.execute(probe.insert().values(id=1))
            assert _count_rows(engine1, probe) == 1

        # clone 2: same template => pristine schema, no data
        with cloned_pg_database_context(postgres_container, template_name) as engine2:
            assert _count_rows(engine2, probe) == 0

    # template is dropped on context exit
    maintenance = _maintenance_engine(postgres_container)
    try:
        assert not database_exists(maintenance, template_name)
    finally:
        maintenance.dispose()


def test_stale_template_is_rebuilt(postgres_container: PostgresTestConfig):
    """a template left over from an interrupted session is rebuilt, not reused"""
    template_name = f"tpl_{uuid.uuid4().hex}"
    maintenance = _maintenance_engine(postgres_container)
    with maintenance.connect() as conn:  # AUTOCOMMIT
        conn.execute(sa.text(f"CREATE DATABASE {template_name}"))
    assert database_exists(maintenance, template_name)

    with migrated_pg_template_context(postgres_container, template_name):
        # stale DB was dropped and rebuilt (no error raised), visible inside the context
        assert database_exists(maintenance, template_name)

    # context exit drops the template
    assert not database_exists(maintenance, template_name)
    drop_pg_template(postgres_container, template_name)  # no-op, must not raise
    assert not database_exists(maintenance, template_name)
    maintenance.dispose()
