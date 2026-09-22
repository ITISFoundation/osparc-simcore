# pylint: disable=redefined-outer-name

import uuid
from collections.abc import Iterator

import docker
import pytest
import sqlalchemy as sa
import tenacity
from pydantic import PostgresDsn
from pytest_simcore.helpers.postgres_tools import (
    PostgresTestConfig,
    _is_database_missing_error,
    cloned_pg_database_context,
    database_exists,
    drop_pg_template,
    maintenance_engine_context,
    migrated_pg_template_context,
    reset_database_from_template,
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


def _engine_to(config: PostgresTestConfig, database: str) -> sa.engine.Engine:
    dsn = str(
        PostgresDsn.build(
            scheme="postgresql+psycopg2",
            username=config["user"],
            password=config["password"],
            host=config["host"],
            port=int(config["port"]),
            path=database,
        )
    )
    return sa.create_engine(dsn)


def _count_rows(engine: sa.engine.Engine, table: sa.Table) -> int:
    with engine.connect() as conn:
        return int(conn.execute(sa.select(sa.func.count()).select_from(table)).scalar())


def test_is_database_missing_error_only_matches_postgres_undefined_database():
    class _DatabaseMissingError:
        pgcode = "3D000"

    missing = sa.exc.ProgrammingError("statement", {}, _DatabaseMissingError())
    other = sa.exc.ProgrammingError("statement", {}, RuntimeError("other error"))

    assert _is_database_missing_error(missing)
    assert not _is_database_missing_error(other)


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
    with maintenance_engine_context(postgres_container) as maintenance:
        assert not database_exists(maintenance, template_name)


def test_clone_from_template_with_attached_sessions_on_source(
    postgres_container: PostgresTestConfig,
):
    """cloning must tolerate backends attached to the template source (regression for
    'CREATE DATABASE ... TEMPLATE': ObjectInUse 'source database is being accessed by
    other users', seen in CI when service engines keep pooled connections open)"""
    template_name = f"tpl_{uuid.uuid4().hex}"
    with migrated_pg_template_context(postgres_container, template_name):
        # keep sessions attached to the template source while cloning
        attached1 = _engine_to(postgres_container, template_name)
        attached2 = _engine_to(postgres_container, template_name)
        conn1 = attached1.connect()
        conn2 = attached2.connect()
        try:
            with (
                cloned_pg_database_context(postgres_container, template_name) as engine,
                engine.begin() as conn,
            ):
                conn.execute(sa.text("CREATE TABLE attached_probe (id int)"))
            # exit re-clone also runs with the source still attached
        finally:
            conn1.close()
            conn2.close()
            attached1.dispose()
            attached2.dispose()


def test_stale_template_is_rebuilt(postgres_container: PostgresTestConfig):
    """a template left over from an interrupted session is rebuilt, not reused"""
    template_name = f"tpl_{uuid.uuid4().hex}"
    with maintenance_engine_context(postgres_container) as maintenance:
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


def test_reset_database_from_template_with_attached_target_sessions(
    postgres_container: PostgresTestConfig,
):
    """resetting must tolerate live sessions attached to the *target* database (regression
    for races with a live stack's pooled connections, the exact hazard
    'reset_database_from_template' guards against by closing the target to new
    connections before terminating its backends)"""
    template_name = f"tpl_{uuid.uuid4().hex}"
    target_name = f"tgt_{uuid.uuid4().hex}"
    probe = sa.Table(
        "reset_probe",
        sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True),
    )

    with maintenance_engine_context(postgres_container) as maintenance, maintenance.connect() as conn:  # AUTOCOMMIT
        conn.execute(sa.text(f"CREATE DATABASE {target_name}"))

    try:
        with migrated_pg_template_context(postgres_container, template_name):
            # seed the target with data that the reset must wipe
            target_engine = _engine_to(postgres_container, target_name)
            probe.metadata.create_all(target_engine, tables=[probe])
            with target_engine.begin() as conn:
                conn.execute(probe.insert().values(id=1))
            assert _count_rows(target_engine, probe) == 1

            # keep a session attached to the target while it is reset
            attached = _engine_to(postgres_container, target_name)
            attached_conn = attached.connect()
            target_config: PostgresTestConfig = {**postgres_container, "database": target_name}
            try:
                reset_database_from_template(target_config, template_name)
            finally:
                attached_conn.close()
                attached.dispose()
            target_engine.dispose()

            # target is a fresh, empty clone: the seeded table is gone ...
            fresh_engine = _engine_to(postgres_container, target_name)
            try:
                with fresh_engine.connect() as conn:
                    assert not conn.execute(
                        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name = 'reset_probe'")
                    ).scalar()
            finally:
                fresh_engine.dispose()

            # ... and ALLOW_CONNECTIONS was restored: a brand-new connection succeeds
            new_engine = _engine_to(postgres_container, target_name)
            with new_engine.connect():
                pass
            new_engine.dispose()
    finally:
        drop_pg_template(postgres_container, target_name)


def test_cloned_database_is_dropped_not_recreated_on_exit(postgres_container: PostgresTestConfig):
    """the target is left dropped once the context exits; the next entry re-clones it (no
    eager recreate on exit, since the caller may not re-enter until much later, if at all)"""
    template_name = f"tpl_{uuid.uuid4().hex}"
    with migrated_pg_template_context(postgres_container, template_name):
        with cloned_pg_database_context(postgres_container, template_name):
            pass

        with maintenance_engine_context(postgres_container) as maintenance:
            assert not database_exists(maintenance, postgres_container["database"])

        # next entry re-clones it from the template without error
        with cloned_pg_database_context(postgres_container, template_name) as engine, engine.connect():
            pass
