import uuid as uuidlib
from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from starlette.status import (HTTP_201_CREATED, HTTP_204_NO_CONTENT,
                              HTTP_409_CONFLICT)

from ..schemas import schemas_dags as schemas

## from ..crud import crud_dags as crud

router = APIRouter()


@router.get("/dags",
    response_model=List[schemas.DAG]
    )
async def list_DAGs(
    page_token: Optional[str] = Query(None, description="Requests a specific page of the list results"),
    page_size: int = Query(0, ge=0, description="Maximum number of results to be returned by the server"),
    order_by: Optional[str] = Query(None, description="Sorts in ascending order comma-separated fields")
    ):
    # List is suited to data from a single collection that is bounded in size and not cached


    # Applicable common patterns
    # SEE pagination: https://cloud.google.com/apis/design/design_patterns#list_pagination
    # SEE sorting https://cloud.google.com/apis/design/design_patterns#sorting_order

    # Applicable naming conventions
    # TODO: filter: https://cloud.google.com/apis/design/naming_convention#list_filter_field
    # SEE response: https://cloud.google.com/apis/design/naming_convention#list_response

    print(page_token)
    print(page_size)
    print(order_by)


@router.get("/dags:batchGet"
    )
async def batch_get_DAGs():
    raise NotImplementedError()


@router.get("/dags:search"
    )
async def search_DAGs():
    # A method that takes multiple resource IDs and returns an object for each of those IDs
    # Alternative to List for fetching data that does not adhere to List semantics, such as services.search.
    #https://cloud.google.com/apis/design/standard_methods#list
    raise NotImplementedError()




# GET --------------

@router.get("/dags/{dag_id}",
    response_model=schemas.DAG
    )
async def get_DAG(dag_id: int):
    raise NotImplementedError()
    ### return schemas.DAG(f"node {dag_id} in collection")




# CREATE --------------
@router.post("/dags",
    response_model=schemas.DAG,
    status_code=HTTP_201_CREATED,
    response_description="Successfully created"
    )
async def create_DAG(node: schemas.DAGIn=Body(None)):
    raise NotImplementedError()
    # ...
    if node.id:
        # client-assigned resouce name
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=f"Node {node.id} already exists")

    node = schemas.DAG(uuidlib.uuid4(), "new")
    # crud.set_DAG(node.id, node)
    return node




# UPDATE  --------------
@router.patch("/dags/{dag_id}",
    response_model=schemas.DAG
    )
async def udpate_DAG(dag_id: int, *, node: schemas.DAGIn):
    # load
    stored_data = crud.get_DAG(dag_id)
    stored_obj = schemas.DAG(**stored_data)

    # update
    update_data = node.dict(exclude_unset=True)
    updated_obj = stored_obj.copy(update=update_data)

    # save
    crud.set_DAG(dag_id, jsonable_encoder(updated_obj))

    return node


# DELETE  --------------
@router.delete("/dags/{dag_id}",
    status_code=HTTP_204_NO_CONTENT,
    response_description="Successfully deleted"
    )
async def delete_DAG(dag_id: int):
    print(f"Node {dag_id} deleted")

    #If the Delete method immediately removes the resource, it should return an empty response.
    #If the Delete method initiates a long-running operation, it should return the long-running operation.
    #If the Delete method only marks the resource as being deleted, it should return the updated resource.
