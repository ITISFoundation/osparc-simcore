from typing import List

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query

from . import crud
from . import db
from . import schemas

router = APIRouter()

# Dependency
async def get_conx(engine: db.Engine = Depends(db.get_engine)):
    # TODO: problem here is retries??
    async with engine.acquire() as conn:
        yield conn


# ROUTES -------------
#
# Binds CRUD to rest-API
#

@router.post("/hi")
async def hello(user: schemas.UserCreate):
    "This is help"
    res =  { "ans": "hi"}
    res.update(user.dict())
    return res


@router.post("/users/", response_model=schemas.User)
async def create_user(user: schemas.UserCreate, conn: db.SAConnection = Depends(get_conx)):
    """ This is the doc for create user
    """
    db_user = await crud.get_user_by_email(conn, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return await crud.create_user(conn, user=user)


@router.get("/users/", response_model=List[schemas.User])
async def read_users(skip: int = Query(0, ge=0), limit: int = 100, conn: db.SAConnection = Depends(get_conx)):
    db.info()
    users = await crud.get_users(conn, skip=skip, limit=limit)
    return users


@router.get("/users/{user_id}", response_model=schemas.User)
async def read_user(user_id: int = Query(0, gt=0), conn: db.SAConnection = Depends(get_conx)):
    db_user = await crud.get_user(conn, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.post("/users/{user_id}/items/", response_model=schemas.Item)
async def create_item_for_user(
    user_id: int, item: schemas.ItemCreate, conn: db.SAConnection = Depends(get_conx)
):
    return await crud.create_user_item(conn, item=item, user_id=user_id)


@router.get("/items/", response_model=List[schemas.Item])
async def read_items(skip: int = Query(0, gt=0), limit: int = 100, conn: db.SAConnection = Depends(get_conx)):
    items = await crud.get_items(conn, skip=skip, limit=limit)
    return items


project_router = router

__all__ = (
    'project_router'
)
