from fastapi import Depends, HTTPException, Request, status
from fastapi.applications import State

from ...services.catalog import CatalogApi


def _get_app_state(request: Request) -> State:
    # TODO: make read-only?
    return request.app.state


def get_catalog_api_client(state: State = Depends(_get_app_state)) -> CatalogApi:
    try:
        client = state.catalog_api
    except AttributeError as err:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Catalog services is disabled",
        ) from err

    return client
