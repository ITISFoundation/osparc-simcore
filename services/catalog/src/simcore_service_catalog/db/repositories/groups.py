import json
from typing import List, Optional

import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from sqlalchemy.sql import and_
from sqlalchemy.sql.expression import select

from ...models.domain.group import Group, GroupAtDB
from ..tables import user_to_groups, groups, GroupType
from ._base import BaseRepository


class GroupsRepository(BaseRepository):
    async def list_user_groups(self, user_id: int) -> List[GroupAtDB]:
        groups_in_db = []
        async for row in self.connection.execute(
            sa.select([groups])
            .select_from(
                user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid),
            )
            .where(user_to_groups.c.uid == user_id)
        ):
            if row:
                groups_in_db.append(GroupAtDB(**row))
        return groups_in_db

    async def get_everyone_group(self) -> GroupAtDB:
        row: RowProxy = await (
            await self.connection.execute(
                sa.select([groups]).where(groups.c.type == GroupType.EVERYONE)
            )
        ).first()
        return GroupAtDB(**row)

    # async def get_service(self, key: str, tag: str, gid: int) -> Optional[DAGAtDB]:
    #     stmt = services.select().where(
    #         and_(services.c.key == key, services.c.tag == tag, services.c.gid == gid)
    #     )
    #     row: RowProxy = await (await self.connection.execute(stmt)).first()
    #     if row:
    #         return ServiceAtDB(**row)
    #     return None

    # async def create_service(self, service: ServiceBase) -> int:
    #     stmt = services.insert().values(
    #         workbench=json.dumps(dag.dict()["workbench"]),
    #         **dag.dict(exclude={"workbench"})
    #     )
    #     new_id: int = await (await self.connection.execute(stmt)).scalar()
    #     return new_id

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
