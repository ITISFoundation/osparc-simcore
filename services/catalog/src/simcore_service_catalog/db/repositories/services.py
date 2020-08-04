from typing import List, Optional

import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from sqlalchemy import literal_column
from sqlalchemy.sql import or_, and_

from ...models.domain.service import ServiceAccessRightsAtDB, ServiceMetaDataAtDB
from ..tables import services_access_rights, services_meta_data
from ._base import BaseRepository


class ServicesRepository(BaseRepository):
    async def list_services(
        self,
        gids: Optional[List[int]] = None,
        execute_access: Optional[bool] = None,
        write_access: Optional[bool] = None,
    ) -> List[ServiceMetaDataAtDB]:
        services_in_db = []

        query = sa.select([services_meta_data])
        if gids or execute_access or write_access:
            query = (
                sa.select([services_meta_data])
                .select_from(services_meta_data.join(services_access_rights))
                .where(
                    and_(
                        or_(*[services_access_rights.c.gid == gid for gid in gids])
                        if gids
                        else True,
                        services_access_rights.c.execute_access
                        if execute_access
                        else True,
                        services_access_rights.c.write_access if write_access else True,
                    )
                )
            )

        async for row in self.connection.execute(query):
            if row:
                services_in_db.append(ServiceMetaDataAtDB(**row))
        return services_in_db

    # async def get_service(self, key: str, tag: str, gid: int) -> Optional[DAGAtDB]:
    #     stmt = services.select().where(
    #         and_(services.c.key == key, services.c.tag == tag, services.c.gid == gid)
    #     )
    #     row: RowProxy = await (await self.connection.execute(stmt)).first()
    #     if row:
    #         return ServiceAccessRightsAtDB(**row)
    #     return None

    async def create_service(
        self,
        new_service: ServiceMetaDataAtDB,
        new_service_access_rights: ServiceAccessRightsAtDB,
    ) -> ServiceMetaDataAtDB:
        row: RowProxy = await (
            await self.connection.execute(
                # pylint: disable=no-value-for-parameter
                services_meta_data.insert()
                .values(**new_service.dict(by_alias=True))
                .returning(literal_column("*"))
            )
        ).first()
        created_service = ServiceMetaDataAtDB(**row)
        await self.connection.execute(
            # pylint: disable=no-value-for-parameter
            services_access_rights.insert().values(
                **new_service_access_rights.dict(by_alias=True)
            )
        )
        return created_service

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
