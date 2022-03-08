from aiohttp.web import Application
from aiopg.sa import Engine

from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.models.project_networks import project_networks
from models_library.project_networks import NetworksWithAliases, ProjectNetworks
from sqlalchemy.sql import select
from models_library.projects import ProjectID
from sqlalchemy.dialects.postgresql import insert as pg_insert


def _get_engine(app: Application) -> Engine:
    engine = app.get(APP_DB_ENGINE_KEY)
    assert engine  # nosec
    return engine


async def get_project_networks(
    app: Application, project_id: ProjectID
) -> ProjectNetworks:
    """Gets existing project_networks entry or returns an empty one"""

    async with _get_engine(app).acquire() as connection:
        query = select([project_networks]).where(
            project_networks.c.project_uuid == f"{project_id}"
        )
        result = await connection.execute(query)
        project_networks_row = await result.first()

        if project_networks_row is None:
            return ProjectNetworks.parse_obj(
                dict(project_uuid=project_id, networks_with_aliases={})
            )

        return ProjectNetworks.parse_obj(project_networks_row)


async def update_project_networks(
    app: Application, project_id: ProjectID, networks_with_aliases: NetworksWithAliases
) -> None:
    project_networks_to_insert = ProjectNetworks.parse_obj(
        dict(project_uuid=project_id, networks_with_aliases=networks_with_aliases)
    )

    async with _get_engine(app).acquire() as connection:
        row_data = project_networks_to_insert.dict()
        insert_stmt = pg_insert(project_networks).values(**row_data)
        upsert_snapshot = insert_stmt.on_conflict_do_update(
            constraint=project_networks.primary_key, set_=row_data
        )
        await connection.execute(upsert_snapshot)
