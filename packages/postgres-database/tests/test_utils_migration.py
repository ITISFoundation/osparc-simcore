# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Callable

import pytest
import simcore_postgres_database.cli
from alembic.script.revision import MultipleHeads
from simcore_postgres_database.utils_migration import get_current_head
from sqlalchemy import inspect


def test_migration_has_no_branches():
    try:
        current_head = get_current_head()
        assert current_head
        assert isinstance(current_head, str)
    except MultipleHeads as err:
        pytest.fail(
            f"This project migration expected a single head (i.e. no branches): {err}"
        )


def test_migration_upgrade_downgrade(make_engine: Callable):
    sync_engine = make_engine(is_async=False)
    assert sync_engine
    assert simcore_postgres_database.cli.discover.callback
    assert simcore_postgres_database.cli.upgrade.callback
    dsn = sync_engine.url
    # upgrade...
    simcore_postgres_database.cli.discover.callback(
        user=dsn.username,
        password=dsn.password,
        host=dsn.host,
        database=dsn.database,
        port=dsn.port,
    )
    simcore_postgres_database.cli.upgrade.callback("head")
    # downgrade...
    assert simcore_postgres_database.cli.downgrade.callback
    assert simcore_postgres_database.cli.clean.callback
    simcore_postgres_database.cli.downgrade.callback("base")
    simcore_postgres_database.cli.clean.callback()  # just cleans discover cache
    inspector = inspect(sync_engine)

    assert inspector.get_table_names() == [
        "alembic_version"
    ], "Only the alembic table should remain, please check!!!"
