from aiohttp.web import Application
from aiopg.sa import Engine

from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.models.sharing_networks import sharing_networks
from models_library.sharing_networks import NetworksWithAliases, SharingNetworks
from sqlalchemy.sql import select
from models_library.projects import ProjectID
from sqlalchemy.dialects.postgresql import insert as pg_insert


def _get_engine(app: Application) -> Engine:
    engine = app.get(APP_DB_ENGINE_KEY)
    assert engine  # nosec
    return engine


async def get_sharing_networks(
    app: Application, project_id: ProjectID
) -> SharingNetworks:
    """Gets existing sharing_networks entry or returns an empty one"""

    async with _get_engine(app).acquire() as connection:
        query = select([sharing_networks]).where(
            sharing_networks.c.project_uuid == f"{project_id}"
        )
        result = await connection.execute(query)
        sharing_networks_row = await result.first()

        if sharing_networks_row is None:
            return SharingNetworks.create_empty(project_uuid=project_id)

        return SharingNetworks.parse_obj(sharing_networks_row)


async def update_sharing_networks(
    app: Application, project_id: ProjectID, networks_with_aliases: NetworksWithAliases
) -> None:
    sharing_networks_to_insert = SharingNetworks.create(
        project_uuid=project_id, networks_with_aliases=networks_with_aliases
    )

    async with _get_engine(app).acquire() as connection:
        row_data = sharing_networks_to_insert.dict()
        insert_stmt = pg_insert(sharing_networks).values(**row_data)
        upsert_snapshot = insert_stmt.on_conflict_do_update(
            constraint=sharing_networks.primary_key, set_=row_data
        )
        await connection.execute(upsert_snapshot)
