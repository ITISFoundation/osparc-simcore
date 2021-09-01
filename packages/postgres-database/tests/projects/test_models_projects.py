# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

# from sqlalchemy.dialects.postgresql.base import UUID <<<<<<<<<

from uuid import UUID

from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from aiopg.sa.result import RowProxy
from simcore_postgres_database.models.projects import projects, projects_trash
from sqlalchemy.sql.expression import exists

# concepts/prototypes


async def trash(project_uuid: UUID, conn: SAConnection):
    # TODO: move row from projects -> projects_trash
    ...


async def restore(project_uuid: UUID, conn: SAConnection):
    # TODO: move from projects_trash -> projects except the 'deleted' column
    ...


async def test_trash_and_restore_a_project(
    pg_engine: Engine, project: RowProxy, conn: SAConnection
):
    async def _in(table) -> bool:
        return bool(await conn.scalar(exists().where(table.c.uuid == project.uuid)))

    # -------
    # TODO: trash a project and restore it back

    assert not await _in(projects_trash)
    assert await _in(projects)

    await trash(project.uuid, conn)

    assert await _in(projects_trash)
    assert not await _in(projects)

    await restore(project.uuid, conn)

    assert not await _in(projects_trash)
    assert await _in(projects)


async def test_gc_detect_trashes():
    #
    # TODO: gc searches for trash tables and has a flushing mechanism based
    # defined by some trash policy e.g. age,
    #
    assert False


#
# TODO: what about the linked tables?? probably need to create trashes for
#       those
#
#
