import uuid as uuidlib
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from starlette.status import (HTTP_201_CREATED, HTTP_204_NO_CONTENT,
                              HTTP_409_CONFLICT)

from .. import db
from ..crud import crud_dags as crud
from ..schemas import schemas_dags as schemas

router = APIRouter()


@router.get("/dags",
    response_model=List[schemas.DAGOut]
    )
async def list_dags(
    page_token: Optional[str] = Query(None, description="Requests a specific page of the list results"),
    page_size: int = Query(0, ge=0, description="Maximum number of results to be returned by the server"),
    order_by: Optional[str] = Query(None, description="Sorts in ascending order comma-separated fields"),
    conn: db.SAConnection = Depends(db.get_cnx)
    ):

    # List is suited to data from a single collection that is bounded in size and not cached

    # Applicable common patterns
    # SEE pagination: https://cloud.google.com/apis/design/design_patterns#list_pagination
    # SEE sorting https://cloud.google.com/apis/design/design_patterns#sorting_order

    # Applicable naming conventions
    # TODO: filter: https://cloud.google.com/apis/design/naming_convention#list_filter_field
    # SEE response: https://cloud.google.com/apis/design/naming_convention#list_response

    #print(page_token)
    #print(page_size)
    #print(order_by)
    dags = await crud.list_dags(conn)
    return dags




@router.get("/dags:batchGet"
    )
async def batch_get_dags():
    raise NotImplementedError()


@router.get("/dags:search"
    )
async def search_dags():
    # A method that takes multiple resource IDs and returns an object for each of those IDs
    # Alternative to List for fetching data that does not adhere to List semantics, such as services.search.
    #https://cloud.google.com/apis/design/standard_methods#list
    raise NotImplementedError()




# GET --------------

@router.get("/dags/{dag_id}",
    response_model=schemas.DAGOut
    )
async def get_dag(dag_id: int):
    raise NotImplementedError()
    ### return schemas.DAG(f"dag {dag_id} in collection")




# CREATE --------------
@router.post("/dags",
    response_model=int,
    status_code=HTTP_201_CREATED,
    response_description="Successfully created"
    )
async def create_dag(
    dag: schemas.DAGIn=Body(None),
    conn: db.SAConnection = Depends(db.get_cnx)
    ):

    if dag.version == "0.0.0" and dag.key=="foo":
        # client-assigned resouce name
        raise HTTPException(
            status_code=HTTP_409_CONFLICT,
            detail=f"DAG {dag.key}:{dag.version} already exists"
        )

    # FIXME: conversion DAG (issue with workbench being json in orm and dict in schema)
    dag_id = await crud.create_dag(conn, dag)
    # TODO: no need to return since there is not extra info?, perhaps return
    return dag_id



# UPDATE  --------------
@router.patch("/dags/{dag_id}",
    response_model=schemas.DAGOut
    )
async def udpate_dag(dag_id: int,
    dag: schemas.DAGIn=Body(None),
    conn: db.SAConnection = Depends(db.get_cnx) ):

    with conn.begin():
        await crud.update_dag(conn, dag_id, dag)
        updated_dag = await crud.get_dag(conn, dag_id)

    return updated_dag



@router.put("/dags/{dag_id}",
    response_model=Optional[schemas.DAGOut]
    )
async def replace_dag(dag_id: int,
    dag: schemas.DAGIn = Body(...),
    conn: db.SAConnection = Depends(db.get_cnx) ):

    await crud.replace_dag(conn, dag_id, dag)

    return None


# DELETE  --------------
@router.delete("/dags/{dag_id}",
    status_code=HTTP_204_NO_CONTENT,
    response_description="Successfully deleted"
    )
async def delete_dag(dag_id: int,
    conn: db.SAConnection = Depends(db.get_cnx) ):
    # If the Delete method immediately removes the resource, it should return an empty response.
    # If the Delete method initiates a long-running operation, it should return the long-running operation.
    # If the Delete method only marks the resource as being deleted, it should return the updated resource.
    await crud.delete_dag(conn, dag_id)
