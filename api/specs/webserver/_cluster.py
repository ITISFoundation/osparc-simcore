from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.clusters import (
    ClusterCreate,
    ClusterDetails,
    ClusterGet,
    ClusterPatch,
    ClusterPathParams,
    ClusterPing,
)
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "clusters",
    ],
)


@router.get(
    "/clusters",
    operation_id="list_clusters",
    response_model=Envelope[list[ClusterGet]],
)
def list_clusters():
    ...


@router.post(
    "/clusters",
    operation_id="create_cluster",
    response_model=Envelope[ClusterGet],
    status_code=status.HTTP_201_CREATED,
)
def create_cluster(
    _insert: ClusterCreate,
):
    ...


@router.post(
    "/clusters:ping",
    operation_id="ping_cluster",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
def ping_cluster(
    _ping: ClusterPing,
):
    """
    Test connectivity with cluster
    """


@router.get(
    "/clusters/{cluster_id}",
    operation_id="get_cluster",
    response_model=Envelope[ClusterGet],
)
def get_cluster(_path_params: Annotated[ClusterPathParams, Depends()]):
    ...


@router.patch(
    "/clusters/{cluster_id}",
    operation_id="update_cluster",
    response_model=Envelope[ClusterGet],
)
def update_cluster(
    _path_params: Annotated[ClusterPathParams, Depends()], _update: ClusterPatch
):
    ...


@router.delete(
    "/clusters/{cluster_id}",
    operation_id="delete_cluster",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_cluster(
    _path_params: Annotated[ClusterPathParams, Depends()],
):
    ...


@router.get(
    "/clusters/{cluster_id}/details",
    operation_id="get_cluster_details",
    response_model=Envelope[ClusterDetails],
)
def get_cluster_details(
    _path_params: Annotated[ClusterPathParams, Depends()],
):
    ...


@router.post(
    "/clusters/{cluster_id}:ping",
    operation_id="ping_cluster_cluster_id",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
def ping_cluster_cluster_id(
    _path_params: Annotated[ClusterPathParams, Depends()],
):
    """
    Tests connectivity with cluster
    """
