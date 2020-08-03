from typing import List, Optional

import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from sqlalchemy.sql import or_
from sqlalchemy import literal_column

from ...models.domain.service import ServiceAtDB
from ..tables import services
from ._base import BaseRepository


class ServicesRepository(BaseRepository):
    async def list_services(
        self, gids: Optional[List[int]] = None
    ) -> List[ServiceAtDB]:
        services_in_db = []
        query = sa.select([services])
        if gids:
            query = sa.select([services]).where(
                or_(*[services.c.gid == gid for gid in gids])
            )
        async for row in self.connection.execute(query):
            if row:
                services_in_db.append(ServiceAtDB(**row))
        return services_in_db

    async def list_distinct_services(self) -> List[ServiceAtDB]:
        services_in_db = []
        query = sa.select([services]).distinct(services.c.key, services.c.tag)
        async for row in self.connection.execute(query):
            if row:
                services_in_db.append(ServiceAtDB(**row))
        return services_in_db

    # async def get_service(self, key: str, tag: str, gid: int) -> Optional[DAGAtDB]:
    #     stmt = services.select().where(
    #         and_(services.c.key == key, services.c.tag == tag, services.c.gid == gid)
    #     )
    #     row: RowProxy = await (await self.connection.execute(stmt)).first()
    #     if row:
    #         return ServiceAtDB(**row)
    #     return None

    async def create_service(self, new_service: ServiceAtDB) -> ServiceAtDB:
        row: RowProxy = await (
            await self.connection.execute(
                # pylint: disable=no-value-for-parameter
                services.insert()
                .values(**new_service.dict(by_alias=True))
                .returning(literal_column("*"))
            )
        ).first()
        return ServiceAtDB(**row)

    # async def replace_dag(self, dag_id: int, dag: DAGIn):
    #     stmt = (
    #         dags.update()
    #         .values(
    #             workbench=json.dumps(dag.dict()["workbench"]),
    #             **dag.dict(exclude={"workbench"})
    #         )
    #         .where(dags.c.id == dag_id)
    #     )
    #     await self.connection.execute(stmt)

    # async def update_dag(self, dag_id: int, dag: DAGIn):
    #     patch = dag.dict(exclude_unset=True, exclude={"workbench"})
    #     if "workbench" in dag.__fields_set__:
    #         patch["workbench"] = json.dumps(patch["workbench"])

    #     stmt = sa.update(dags).values(**patch).where(dags.c.id == dag_id)
    #     res = await self.connection.execute(stmt)

    #     # TODO: dev asserts
    #     assert res.returns_rows == False  # nosec

    # async def delete_dag(self, dag_id: int):
    #     stmt = sa.delete(dags).where(dags.c.id == dag_id)
    #     await self.connection.execute(stmt)
