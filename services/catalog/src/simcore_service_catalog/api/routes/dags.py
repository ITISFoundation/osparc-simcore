import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_409_CONFLICT,
    HTTP_501_NOT_IMPLEMENTED,
)

from ...db.repositories.dags import DAGsRepository
from ...models.schemas.dag import DAGIn, DAGOut
from ..dependencies.database import get_repository

router = APIRouter()
log = logging.getLogger(__name__)


@router.get("", response_model=list[DAGOut])
async def list_dags(
    page_token: Optional[str] = Query(
        None, description="Requests a specific page of the list results"
    ),
    page_size: int = Query(
        0, ge=0, description="Maximum number of results to be returned by the server"
    ),
    order_by: Optional[str] = Query(
        None, description="Sorts in ascending order comma-separated fields"
    ),
    dags_repo: DAGsRepository = Depends(get_repository(DAGsRepository)),
):

    # List is suited to data from a single collection that is bounded in size and not cached

    # Applicable common patterns
    # SEE pagination: https://cloud.google.com/apis/design/design_patterns#list_pagination
    # SEE sorting https://cloud.google.com/apis/design/design_patterns#sorting_order

    # Applicable naming conventions
    # TODO: filter: https://cloud.google.com/apis/design/naming_convention#list_filter_field
    # SEE response: https://cloud.google.com/apis/design/naming_convention#list_response
    log.debug("%s %s %s", page_token, page_size, order_by)
    dags = await dags_repo.list_dags()
    return dags


@router.get(":batchGet")
async def batch_get_dags():
    raise HTTPException(
        status_code=HTTP_501_NOT_IMPLEMENTED, detail="Still not implemented"
    )


@router.get(":search")
async def search_dags():
    # A method that takes multiple resource IDs and returns an object for each of those IDs
    # Alternative to List for fetching data that does not adhere to List semantics, such as services.search.
    # https://cloud.google.com/apis/design/standard_methods#list
    raise HTTPException(
        status_code=HTTP_501_NOT_IMPLEMENTED, detail="Still not implemented"
    )


@router.get("/{dag_id}", response_model=DAGOut)
async def get_dag(
    dag_id: int,
    dags_repo: DAGsRepository = Depends(get_repository(DAGsRepository)),
):
    dag = await dags_repo.get_dag(dag_id)
    return dag


@router.post(
    "",
    response_model=int,
    status_code=HTTP_201_CREATED,
    response_description="Successfully created",
)
async def create_dag(
    dag: DAGIn = Body(...),
    dags_repo: DAGsRepository = Depends(get_repository(DAGsRepository)),
):
    assert dag  # nosec

    if dag.version == "0.0.0" and dag.key == "foo":
        # client-assigned resouce name
        raise HTTPException(
            status_code=HTTP_409_CONFLICT,
            detail=f"DAG {dag.key}:{dag.version} already exists",
        )

    # FIXME: conversion DAG (issue with workbench being json in orm and dict in schema)
    dag_id = await dags_repo.create_dag(dag)
    # TODO: no need to return since there is not extra info?, perhaps return
    return dag_id


@router.patch("/{dag_id}", response_model=DAGOut)
async def udpate_dag(
    dag_id: int,
    dag: DAGIn = Body(None),
    dags_repo: DAGsRepository = Depends(get_repository(DAGsRepository)),
):
    async with dags_repo.db_engine.begin():
        await dags_repo.update_dag(dag_id, dag)
        updated_dag = await dags_repo.get_dag(dag_id)

    return updated_dag


@router.put("/{dag_id}", response_model=Optional[DAGOut])
async def replace_dag(
    dag_id: int,
    dag: DAGIn = Body(...),
    dags_repo: DAGsRepository = Depends(get_repository(DAGsRepository)),
):
    await dags_repo.replace_dag(dag_id, dag)


@router.delete(
    "/{dag_id}",
    status_code=HTTP_204_NO_CONTENT,
    response_description="Successfully deleted",
)
async def delete_dag(
    dag_id: int,
    dags_repo: DAGsRepository = Depends(get_repository(DAGsRepository)),
):
    # If the Delete method immediately removes the resource, it should return an empty response.
    # If the Delete method initiates a long-running operation, it should return the long-running operation.
    # If the Delete method only marks the resource as being deleted, it should return the updated resource.
    await dags_repo.delete_dag(dag_id)
