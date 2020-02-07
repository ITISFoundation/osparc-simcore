
#  reusable functions to interact with the data in the database.
from . import db
from . import orm, schemas


async def get_user(conn: db.SAConnection, user_id: int):
    query = orm.users.select().where(orm.users.c.id == user_id)
    res: db.ResultProxy = await conn.execute(query)
    row: db.RowProxy = await res.first()
    #return db.query(orm.User).filter(orm.User.id == user_id).first()
    return orm.User(**row) if row else None


async def get_user_by_email(conn: db.SAConnection, email: str):
    #return db.query(orm.User).filter(orm.User.email == email).first()
    q = orm.users.select().where(orm.users.c.email == email)
    row: db.RowProxy = await (await conn.execute(q)).first()
    return orm.User(**row) if row else None


async def get_users(conn: db.SAConnection, skip: int = 0, limit: int = 100):
    # return db.query(orm.User).offset(skip).limit(limit).all()
    # TODO: offset??
    rows: List[db.RowProxy] = []
    async for row in conn.execute(orm.users.select()):
        rows.append(row)
        if len(rows)>=limit:
            break
    return [orm.User(**r) if r else None for r in rows]


async def create_user(conn: db.SAConnection, user: schemas.UserCreate):
    q = orm.users.insert().values(
        email=user.email,
        hashed_password=user.password + "notreallyhashed"
    )
    await conn.execute(q)
    row: db.RowProxy = await(await conn.execute(orm.users.select())).first()
    return orm.User(**row) if row else None


async def get_items(conn: db.SAConnection, skip: int = 0, limit: int = 100):
    #return db.query(orm.Item).offset(skip).limit(limit).all()
    rows: List[db.RowProxy] = []
    async for row in conn.execute(orm.items.select()):
        rows.append(row)
        if len(rows) >= limit:
            break
    return [orm.Item(**r) for r in rows]


async def create_user_item(conn: db.SAConnection, item: schemas.ItemCreate, user_id: int):
    q = orm.items.insert().values(**item.dict(), owner_id=user_id)
    await conn.execute(q)
    # TODO: more efficient way of doing this?
    row: db.RowProxy = await(await conn.execute(orm.items.select())).first()
    return orm.Item(**row)

    #db_item = orm.Item()
    #db.add(db_item)
    #db.commit()
    #db.refresh(db_item)
    #return db_item
