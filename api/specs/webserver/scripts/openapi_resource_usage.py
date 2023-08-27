""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum

from _common import (
    CURRENT_DIR,
    assert_handler_signature_against_model,
    create_openapi_specs,
)
from fastapi import FastAPI, Query
from models_library.api_schemas_webserver.resource_usage import ServiceRunGet
from models_library.generics import Envelope
from models_library.rest_pagination import DEFAULT_NUMBER_OF_ITEMS_PER_PAGE
from models_library.wallets import WalletID
from pydantic import NonNegativeInt
from simcore_service_webserver.resource_usage._service_runs_handlers import (
    _ListServicesPathParams,
)

app = FastAPI(redoc_url=None)

TAGS: list[str | Enum] = ["usage"]


#
# API entrypoints
#


@app.get(
    "/resource-usage/services",
    response_model=Envelope[list[ServiceRunGet]],
    tags=TAGS,
    operation_id="list_resource_usage_services",
    summary="Retrieve finished and currently running user services (user and product are taken from context, optionally wallet_id parameter might be provided)",
)
async def list_resource_usage_services(
    wallet_id: WalletID = Query(None),
    limit: int = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    offset: NonNegativeInt = 0,
):
    ...


assert_handler_signature_against_model(
    list_resource_usage_services, _ListServicesPathParams
)


if __name__ == "__main__":

    create_openapi_specs(app, CURRENT_DIR.parent / "openapi-resource-usage.yaml")
