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
from fastapi import FastAPI
from models_library.api_schemas_webserver.resource_usage import ContainerGet
from models_library.generics import Envelope
from models_library.rest_pagination import DEFAULT_NUMBER_OF_ITEMS_PER_PAGE
from pydantic import NonNegativeInt
from simcore_service_webserver.resource_usage._containers_handlers import (
    _ListContainersPathParams,
)

app = FastAPI(redoc_url=None)

TAGS: list[str | Enum] = ["usage"]


#
# API entrypoints
#


@app.get(
    "/resource-usage/containers",
    response_model=Envelope[list[ContainerGet]],
    tags=TAGS,
    operation_id="list_resource_usage_containers",
    summary="Retrieve containers that were running for a user and product taken from context.",
)
async def list_resource_usage_containers(
    limit: int = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE, offset: NonNegativeInt = 0
):
    ...


assert_handler_signature_against_model(
    list_resource_usage_containers, _ListContainersPathParams
)


if __name__ == "__main__":

    create_openapi_specs(app, CURRENT_DIR.parent / "openapi-resource-usage.yaml")
