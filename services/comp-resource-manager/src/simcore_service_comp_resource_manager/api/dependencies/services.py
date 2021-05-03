""" Dependences with any other services (except webserver)

"""
from typing import Callable, Type

from fastapi import HTTPException, Request, status

from ...utils.client_base import BaseServiceClientApi


def get_api_client(client_type: Type[BaseServiceClientApi]) -> Callable:
    """
    Retrieves API client from backend services EXCEPT web-server (see dependencies/webserver)

    Usage:

        director_client: DirectorApi = Depends(get_api_client(DirectorApi)),
        catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
        storage_client: StorageApi = Depends(get_api_client(StorageApi)),
    """
    assert issubclass(client_type, BaseServiceClientApi)  # nosec

    def _get_client_from_app(request: Request) -> client_type:
        client_obj = client_type.get_instance(request.app)
        if client_obj is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{client_type.service_name.title()} service was disabled",
            )

        assert isinstance(client_obj, client_type)  # nosec
        return client_obj

    return _get_client_from_app
