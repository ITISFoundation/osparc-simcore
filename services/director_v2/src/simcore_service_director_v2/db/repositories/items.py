#  reusable functions to interact with the data in the database.
from typing import List

from aiopg.sa.result import RowProxy

from .. import orm
from ._base import BaseRepository


class ItemsRepository(BaseRepository):
    async def list_not_detailed(self, skip: int = 0, limit: int = 100):
        # return db.query(orm.Item).offset(skip).limit(limit).all()
        rows: List[RowProxy] = []
        async for row in self.connection.execute(orm.items.select()):
            rows.append(row)
            if len(rows) >= limit:
                break
        return [orm.Item(**r) for r in rows]

    async def get_item(self, id: int):
        pass

    # async def create_user_item(self, item: schemas.ItemCreate, user_id: int):
    #     q = orm.items.insert().values(**item.dict(), owner_id=user_id)
    #     await self.connection.execute(q)
    #     # TODO: more efficient way of doing this?
    #     row: db.RowProxy = await (
    #         await self.connection.execute(orm.items.select())
    #     ).first()
    #     return orm.Item(**row)

    #     # db_item = orm.Item()
    # db.add(db_item)
    # db.commit()
    # db.refresh(db_item)
    # return db_item
