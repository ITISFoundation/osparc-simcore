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
        async with self.db_engine.acquire() as conn:
            async for row in conn.execute(dags.select()):
                dagraphs.append(DAGAtDB(**row))
        return dagraphs

    async def get_dag(self, dag_id: int) -> Optional[DAGAtDB]:
        async with self.db_engine.acquire() as conn:
            row: RowProxy = await (
                await conn.execute(dags.select().where(dags.c.id == dag_id))
            ).first()
        if row:
            return DAGAtDB(**row)

    async def create_dag(self, dag: DAGIn) -> int:
        async with self.db_engine.acquire() as conn:
            new_id: int = await (
                await conn.execute(
                    dags.insert().values(
                        workbench=dag.json(include={"workbench"}),
                        **dag.dict(exclude={"workbench"})
                    )
                )
            ).scalar()
            return new_id

    async def replace_dag(self, dag_id: int, dag: DAGIn):
        async with self.db_engine.acquire() as conn:
            await conn.execute(
                dags.update()
                .values(
                    workbench=dag.json(include={"workbench"}),
                    **dag.dict(exclude={"workbench"})
                )
                .where(dags.c.id == dag_id)
            )

    async def update_dag(self, dag_id: int, dag: DAGIn):
        patch = dag.dict(exclude_unset=True, exclude={"workbench"})
        if "workbench" in dag.__fields_set__:
            patch["workbench"] = json.dumps(patch["workbench"])
        async with self.db_engine.acquire() as conn:
            res = await conn.execute(
                sa.update(dags).values(**patch).where(dags.c.id == dag_id)
            )

            # TODO: dev asserts
            assert res.returns_rows == False  # nosec

    async def delete_dag(self, dag_id: int):
        async with self.db_engine.acquire() as conn:
            await conn.execute(sa.delete(dags).where(dags.c.id == dag_id))
