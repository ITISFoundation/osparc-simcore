import json
from typing import List, Optional

import sqlalchemy as sa
from aiopg.sa.result import RowProxy

from ...models.domain.dag import DAGAtDB
from ...models.schemas.dag import DAGIn
from ..tables import dags
from ._base import BaseRepository


class DAGsRepository(BaseRepository):
    async def list_dags(self) -> List[DAGAtDB]:
        dagraphs = []
        async for row in self.connection.execute(dags.select()):
            if row:
                dagraphs.append(DAGAtDB(**row))
        return dagraphs

    async def get_dag(self, dag_id: int) -> Optional[DAGAtDB]:
        stmt = dags.select().where(dags.c.id == dag_id)
        row: RowProxy = await (await self.connection.execute(stmt)).first()
        if row:
            return DAGAtDB(**row)
        return None

    async def create_dag(self, dag: DAGIn) -> int:
        stmt = dags.insert().values(
            workbench=json.dumps(dag.dict()["workbench"]),
            **dag.dict(exclude={"workbench"})
        )
        new_id: int = await (await self.connection.execute(stmt)).scalar()
        return new_id

    async def replace_dag(self, dag_id: int, dag: DAGIn):
        stmt = (
            dags.update()
            .values(
                workbench=json.dumps(dag.dict()["workbench"]),
                **dag.dict(exclude={"workbench"})
            )
            .where(dags.c.id == dag_id)
        )
        await self.connection.execute(stmt)

    async def update_dag(self, dag_id: int, dag: DAGIn):
        patch = dag.dict(exclude_unset=True, exclude={"workbench"})
        if "workbench" in dag.__fields_set__:
            patch["workbench"] = json.dumps(patch["workbench"])

        stmt = sa.update(dags).values(**patch).where(dags.c.id == dag_id)
        res = await self.connection.execute(stmt)

        # TODO: dev asserts
        assert res.returns_rows == False  # nosec

    async def delete_dag(self, dag_id: int):
        stmt = sa.delete(dags).where(dags.c.id == dag_id)
        await self.connection.execute(stmt)
