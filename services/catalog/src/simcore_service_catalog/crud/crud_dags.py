import json
from typing import List, Optional

import sqlalchemy as sa

from .. import db
from ..orm import orm_dags as orm
from ..schemas import schemas_dags as schemas


async def get_dag(conn: db.SAConnection, dag_id: int) -> Optional[orm.DAG]:
    query = orm.dags.select().where(orm.dags.c.id == dag_id)
    row: db.RowProxy = await (await conn.execute(query)).first()
    if row:
        return orm.DAG(**row)
    return None


async def list_dags(conn: db.SAConnection) -> List[orm.DAG]:
    dags = []
    async for row in conn.execute(orm.dags.select()):
        if row:
            dags.append(orm.DAG(**row))
    return dags


async def create_dag(conn: db.SAConnection, dag: schemas.DAGIn):
    q = orm.dags.insert().values(
        key = dag.key,
        version = dag.version,
        name = dag.name,
        description = dag.description,
        contact = dag.contact,
        workbench = json.dumps(dag.dict()['workbench'])
    )

    new_id: int = await(await conn.execute(q)).scalar()

    # TODO: convert
    q = orm.dags.select( (orm.dags.c.id == new_id) )
    row: db.RowProxy = await(await conn.execute(q)).first()
    assert row
    #if row:
    #    _dag = orm.DAG(**row)
    return new_id
