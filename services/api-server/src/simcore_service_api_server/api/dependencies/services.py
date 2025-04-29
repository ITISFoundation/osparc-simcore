"""Dependences with any other services (except webserver)"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from servicelib.rabbitmq import RabbitMQRPCClient
from simcore_service_api_server._service_studies import StudiesService

from ..._service_solvers import SolverService
from ...services_rpc.catalog import CatalogService
from ...services_rpc.wb_api_server import WbApiRpcClient
from ...utils.client_base import BaseServiceClientApi
from .rabbitmq import get_rabbitmq_rpc_client
from .webserver_rpc import get_wb_api_rpc_client


def get_api_client(client_type: type[BaseServiceClientApi]) -> Callable:
    """
    Retrieves API client from backend services EXCEPT web-server (see dependencies/webserver)

    Usage:

        director_client: DirectorApi = Depends(get_api_client(DirectorApi)),
        storage_client: StorageApi = Depends(get_api_client(StorageApi)),
    """
    assert issubclass(client_type, BaseServiceClientApi)  # nosec

    def _get_client_from_app(request: Request) -> BaseServiceClientApi:
        client_obj = client_type.get_instance(request.app)
        if client_obj is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{client_type.service_name.title()} service was disabled",
            )

        assert isinstance(client_obj, client_type)  # nosec
        return client_obj

    return _get_client_from_app


def get_catalog_service(
    rpc_client: Annotated[RabbitMQRPCClient, Depends(get_rabbitmq_rpc_client)],
):
    """
    "Assembles" the CatalogService layer to the RabbitMQ client
    in the context of the rest controller (i.e. api/dependencies)
    """
    return CatalogService(client=rpc_client)


def get_solver_service(
    catalog_service: Annotated[CatalogService, Depends(get_catalog_service)],
    webserver_client: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
) -> SolverService:
    """
    "Assembles" the SolverService layer to the underlying service and client interfaces
    in the context of the rest controller (i.e. api/dependencies)
    """

    return SolverService(
        catalog_service=catalog_service,
        webserver_client=webserver_client,
    )


def get_studies_service(
    webserver_client: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
) -> StudiesService:
    return StudiesService(
        webserver_client=webserver_client,
    )
