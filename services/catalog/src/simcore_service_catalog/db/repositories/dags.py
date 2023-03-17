import json
from typing import Optional

import sqlalchemy as sa

from ...models.domain.dag import DAGAtDB
from ...models.schemas.dag import DAGIn
from ..tables import dags
from ._base import BaseRepository


class DAGsRepository(BaseRepository):
    async def list_dags(self) -> list[DAGAtDB]:
        dagraphs = []
        async with self.db_engine.connect() as conn:
            async for row in await conn.stream(dags.select()):
                dagraphs.append(DAGAtDB.parse_obj(row))
        return dagraphs

    async def get_dag(self, dag_id: int) -> Optional[DAGAtDB]:
        async with self.db_engine.connect() as conn:
            result = await conn.execute(dags.select().where(dags.c.id == dag_id))
            row = result.first()
        if row:
            return DAGAtDB.from_orm(row)

    async def create_dag(self, dag: DAGIn) -> int:
        async with self.db_engine.begin() as conn:
            new_id: int = await conn.scalar(
                dags.insert().values(
                    workbench=dag.json(include={"workbench"}),
                    **dag.dict(exclude={"workbench"})
                )
            )

            return new_id

    async def replace_dag(self, dag_id: int, dag: DAGIn) -> None:
        async with self.db_engine.begin() as conn:
            await conn.execute(
                dags.update()
                .values(
                    workbench=dag.json(include={"workbench"}),
                    **dag.dict(exclude={"workbench"})
                )
                .where(dags.c.id == dag_id)
            )

    async def update_dag(self, dag_id: int, dag: DAGIn) -> None:
        patch = dag.dict(exclude_unset=True, exclude={"workbench"})
        if "workbench" in dag.__fields_set__:
            patch["workbench"] = json.dumps(patch["workbench"])
        async with self.db_engine.begin() as conn:
            await conn.execute(
                sa.update(dags).values(**patch).where(dags.c.id == dag_id)
            )

    async def delete_dag(self, dag_id: int) -> None:
        async with self.db_engine.begin() as conn:
            await conn.execute(sa.delete(dags).where(dags.c.id == dag_id))
