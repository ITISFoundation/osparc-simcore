import json
from typing import List, Optional

import sqlalchemy as sa

import orm

from .. import db
from ..schemas import schemas_dags as schemas


async def list_dags(conn: db.SAConnection) -> List[schemas.DAGAtDB]:
    dags = []
    async for row in conn.execute(orm.dags.select()):
        if row:
            dags.append(schemas.DAGAtDB(**row))
    return dags


async def get_dag(conn: db.SAConnection, dag_id: int) -> Optional[schemas.DAGAtDB]:
    stmt = orm.dags.select().where(orm.dags.c.id == dag_id)
    row: db.RowProxy = await (await conn.execute(stmt)).first()
    if row:
        return schemas.DAGAtDB(**row)
    return None


async def create_dag(conn: db.SAConnection, dag: schemas.DAGIn):
    stmt = orm.dags.insert().values(
        workbench=json.dumps(dag.dict()["workbench"]), **dag.dict(exclude={"workbench"})
    )
    new_id: int = await (await conn.execute(stmt)).scalar()
    return new_id


async def replace_dag(conn: db.SAConnection, dag_id: int, dag: schemas.DAGIn):
    stmt = (
        orm.dags.update()
        .values(
            workbench=json.dumps(dag.dict()["workbench"]),
            **dag.dict(exclude={"workbench"})
        )
        .where(orm.dags.c.id == dag_id)
    )
    await conn.execute(stmt)


async def update_dag(conn: db.SAConnection, dag_id: int, dag: schemas.DAGIn):
    patch = dag.dict(exclude_unset=True, exclude={"workbench"})
    if "workbench" in dag.__fields_set__:
        patch["workbench"] = json.dumps(patch["workbench"])

    stmt = sa.update(orm.dags).values(**patch).where(orm.dags.c.id == dag_id)
    res = await conn.execute(stmt)

    # TODO: dev asserts
    assert res.returns_rows == False  # nosec


async def delete_dag(conn: db.SAConnection, dag_id: int):
    stmt = sa.delete(orm.dags).where(orm.dags.c.id == dag_id)
    await conn.execute(stmt)
