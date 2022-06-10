from aiopg.sa import SAConnection
from simcore_postgres_database.models.projects import projects as projects_table
from simcore_postgres_database.utils_aiopg_orm import BaseOrm

from ..db_base_repository import BaseRepository


class ProjectsRepository(BaseRepository):

    # TOOL
    class ProjectsOrm(BaseOrm[str]):
        def __init__(self, connection: SAConnection):
            super().__init__(
                projects_table,
                connection,
                readonly={"id", "creation_date", "last_change_date"},
                writeonce={"uuid"},
            )

    async def get_all(self):
        pass

    async def get_one(self):
        pass

    async def create(self):
        pass

    async def update(self):
        pass

    async def delete_all(self):
        pass

    async def delete_one(self):
        pass
