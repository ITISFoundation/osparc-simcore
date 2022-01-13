from contextlib import contextmanager
from copy import deepcopy
from typing import Any, Dict, Iterator

import simcore_postgres_database.cli
import sqlalchemy as sa
from simcore_postgres_database.models.base import metadata


@contextmanager
def migrated_pg_tables_context(
    postgres_config: Dict[str, Any]
) -> Iterator[Dict[str, Any]]:
    """
    Within the context, tables are created and dropped
    using migration upgrade/downgrade routines
    """

    cfg = deepcopy(postgres_config)
    cfg.update(
        dsn="postgresql://{user}:{password}@{host}:{port}/{database}".format(
            **postgres_config
        )
    )

    simcore_postgres_database.cli.discover.callback(**postgres_config)
    simcore_postgres_database.cli.upgrade.callback("head")

    yield cfg

    # downgrades database to zero ---
    #
    # NOTE: This step CANNOT be avoided since it would leave the db in an invalid state
    # E.g. 'alembic_version' table is not deleted and keeps head version or routines
    # like 'notify_comp_tasks_changed' remain undeleted
    #
    simcore_postgres_database.cli.downgrade.callback("base")
    simcore_postgres_database.cli.clean.callback()  # just cleans discover cache

    # FIXME: migration downgrade fails to remove User types
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/1776
    # Added drop_all as tmp fix
    postgres_engine = sa.create_engine(cfg["dsn"])
    metadata.drop_all(bind=postgres_engine)


def is_postgres_responsive(url) -> bool:
    """Check if something responds to ``url``"""
    try:
        engine = sa.create_engine(url)
        conn = engine.connect()
        conn.close()
    except sa.exc.OperationalError:
        return False
    return True
