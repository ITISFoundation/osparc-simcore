from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import db
from ..crud import crud_samples as crud
from ..schemas import schemas_samples as schemas




router = APIRouter()


# ROUTES -------------
#
# Binds CRUD to rest-API
#

@router.post("/users/", response_model=schemas.User)
async def create_user(
        user: schemas.UserCreate,
        conn: db.SAConnection = Depends(db.get_cnx)
    ):
    """ This is the doc for create user
    """
    db_user = await crud.get_user_by_email(conn, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return await crud.create_user(conn, user=user)


@router.get("/users/", response_model=List[schemas.User])
async def read_users(
        skip: int = Query(0, ge=0), limit: int = 100,
        conn: db.SAConnection = Depends(db.get_cnx)
    ):
    db.info()
    users = await crud.get_users(conn, skip=skip, limit=limit)
    return users


@router.get("/users/{user_id}", response_model=schemas.User)
async def read_user(
        user_id: int = Query(0, gt=0),
        conn: db.SAConnection = Depends(db.get_cnx),
    ):
    db_user = await crud.get_user(conn, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.post("/users/{user_id}/items/", response_model=schemas.Item)
async def create_item_for_user(
        user_id: int,
        item: schemas.ItemCreate,
        conn: db.SAConnection = Depends(db.get_cnx),
    ):
    return await crud.create_user_item(conn, item=item, user_id=user_id)


@router.get("/items/", response_model=List[schemas.Item])
async def read_items(
        skip: int = Query(0, gt=0), limit: int = 100,
        conn: db.SAConnection = Depends(db.get_cnx),
    ):
    items = await crud.get_items(conn, skip=skip, limit=limit)
    return items
