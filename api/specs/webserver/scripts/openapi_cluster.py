from typing import Annotated, Any

from fastapi import APIRouter, Depends
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.diagnostics._handlers import (
    AppStatusCheck,
    StatusDiagnosticsGet,
    StatusDiagnosticsQueryParam,
)
from simcore_service_webserver.rest.healthcheck import HealthInfoDict

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "cluster",
    ],
)


@router.get(
    '/clusters',
    response_model=ClustersGetResponse,
    responses={'default': {'model': ClustersGetResponse1}},

)
def list_clusters_handler() -> Union[ClustersGetResponse, ClustersGetResponse1]:
    """
    List my clusters
    """
    pass


@router.post(
    '/clusters',
    response_model=None,
    responses={
        '201': {'model': ClustersPostResponse},
        'default': {'model': ClustersPostResponse1},
    },

)
def create_cluster_handler(
    body: ClustersPostRequest,
) -> Union[None, ClustersPostResponse, ClustersPostResponse1]:
    """
    Create a new cluster
    """
    pass


@router.get(
    '/clusters/{cluster_id}',
    response_model=ClustersClusterIdGetResponse,
    responses={'default': {'model': ClustersClusterIdGetResponse1}},

)
def get_cluster_handler(
    cluster_id: str,
) -> Union[ClustersClusterIdGetResponse, ClustersClusterIdGetResponse1]:
    """
    Gets one cluster
    """
    pass


@router.patch(
    '/clusters/{cluster_id}',
    response_model=ClustersClusterIdPatchResponse,
    responses={'default': {'model': ClustersClusterIdPatchResponse1}},

)
def update_cluster_handler(
    cluster_id: str, body: ClustersClusterIdPatchRequest = ...
) -> Union[ClustersClusterIdPatchResponse, ClustersClusterIdPatchResponse1]:
    """
    Update one cluster
    """
    pass


@router.delete(
    '/clusters/{cluster_id}',
    response_model=None,
    responses={'default': {'model': ClustersClusterIdDeleteResponse}},

)
def delete_cluster_handler(
    cluster_id: str,
) -> Union[None, ClustersClusterIdDeleteResponse]:
    """
    Deletes one cluster
    """
    pass


@router.get(
    '/clusters/{cluster_id}/details',
    response_model=ClustersClusterIdDetailsGetResponse,
    responses={'default': {'model': ClustersClusterIdDetailsGetResponse1}},

)
def get_cluster_details_handler(
    cluster_id: str,
) -> Union[ClustersClusterIdDetailsGetResponse, ClustersClusterIdDetailsGetResponse1]:
    """
    Gets one cluster details
    """
    pass


@router.post(
    '/clusters/{cluster_id}:ping',
    response_model=None,
    responses={'default': {'model': ClustersClusterIdPingPostResponse}},

)
def ping_cluster_cluster_id_handler(
    cluster_id: str,
) -> Union[None, ClustersClusterIdPingPostResponse]:
    """
    test connectivity with cluster
    """
    pass


@router.post(
    '/clusters:ping',
    response_model=None,
    responses={'default': {'model': ClustersPingPostResponse}},

)
def ping_cluster_handler(
    body: ClustersPingPostRequest,
) -> Union[None, ClustersPingPostResponse]:
    """
    test connectivity with cluster
    """
    pass
