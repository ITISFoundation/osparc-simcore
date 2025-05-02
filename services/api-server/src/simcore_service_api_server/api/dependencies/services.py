"""Dependences with any other services (except webserver)"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.rabbitmq import RabbitMQRPCClient

from ..._service_jobs import JobService
from ..._service_programs import ProgramService
from ..._service_solvers import SolverService
from ..._service_studies import StudyService
from ...services_rpc.catalog import CatalogService
from ...services_rpc.wb_api_server import WbApiRpcClient
from ...utils.client_base import BaseServiceClientApi
from .authentication import get_current_user_id, get_product_name
from .rabbitmq import get_rabbitmq_rpc_client
from .webserver_http import AuthSession, get_webserver_session
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
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
):
    """
    "Assembles" the CatalogService layer to the RabbitMQ client
    in the context of the rest controller (i.e. api/dependencies)
    """
    return CatalogService(
        _rpc_client=rpc_client, user_id=user_id, product_name=product_name
    )


def get_job_service(
    web_rest_api: Annotated[AuthSession, Depends(get_webserver_session)],
    web_rpc_api: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> JobService:
    """
    "Assembles" the JobsService layer to the underlying service and client interfaces
    in the context of the rest controller (i.e. api/dependencies)
    """
    return JobService(
        _web_rest_client=web_rest_api,
        _web_rpc_client=web_rpc_api,
        user_id=user_id,
        product_name=product_name,
    )


def get_solver_service(
    catalog_service: Annotated[CatalogService, Depends(get_catalog_service)],
    job_service: Annotated[JobService, Depends(get_job_service)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> SolverService:
    """
    "Assembles" the SolverService layer to the underlying service and client interfaces
    in the context of the rest controller (i.e. api/dependencies)
    """
    return SolverService(
        catalog_service=catalog_service,
        job_service=job_service,
        user_id=user_id,
        product_name=product_name,
    )


def get_study_service(
    job_service: Annotated[JobService, Depends(get_job_service)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> StudyService:
    return StudyService(
        job_service=job_service,
        user_id=user_id,
        product_name=product_name,
    )


def get_program_service(
    catalog_service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> ProgramService:
    return ProgramService(
        catalog_service=catalog_service,
    )
