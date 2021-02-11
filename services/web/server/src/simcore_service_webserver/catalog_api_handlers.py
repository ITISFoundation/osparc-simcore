import json
import sys
from pathlib import Path
from typing import List, Optional

from aiohttp import web
from aiohttp.web import Request, RouteTableDef
from pydantic import ValidationError

from .catalog_api_models import (
    ServiceInputApiOut,
    ServiceInputKey,
    ServiceKey,
    ServiceOutputApiOut,
    ServiceOutputKey,
    ServiceVersion,
)

#
# TODO: uuid instead of key+version?
#

routes = RouteTableDef()


@routes.get("/catalog/services/{service_key:path}/{service_version}/inputs")
async def list_service_inputs_handler(request: Request):
    try:
        # match, parse and validate
        service_key: ServiceKey = request.match_info["service_key"]
        service_version: ServiceVersion = request.match_info["service_version"]

    except (ValidationError, KeyError) as err:
        # TODO: convert into HTTP validation error
        raise web.HTTPUnprocessableEntity() from err

    # Evaluate and return validated model
    response_model = await list_service_inputs(service_key, service_version)

    # format response
    enveloped: str = json.dumps(
        {"data": [json.loads(m.json()) for m in response_model]}
    )

    return web.Response(text=enveloped, content_type="application/json")


async def list_service_inputs(
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> List[ServiceOutputApiOut]:

    # call to catalog and extract inputs here

    return list()


@routes.get("/catalog/services/{service_key:path}/{service_version}/inputs/{input_key}")
async def get_service_input_handler(request: Request):
    try:
        # match, parse and validate
        service_key: ServiceKey = request.match_info["service_key"]
        service_version: ServiceVersion = request.match_info["service_version"]
        input_key: ServiceInputKey = request.match_info["input_key"]

    except (ValidationError, KeyError) as err:
        raise web.HTTPUnprocessableEntity() from err

    # Evaluate and return validated model
    response_model = await get_service_input(service_key, service_version, input_key)

    # format response
    enveloped: str = json.dumps({"data": json.loads(response_model.json())})
    return web.Response(text=enveloped, content_type="application/json")


async def get_service_input(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    input_key: ServiceInputKey,
) -> ServiceInputApiOut:
    # request catalog for a specific input of a service
    return ServiceInputApiOut()


@routes.get("/catalog/services/{service_key:path}/{service_version}/inputs:match")
async def get_compatible_inputs_given_source_output_handler(request: Request):
    try:
        # match, parse and validate
        service_key: ServiceKey = request.match_info["service_key"]
        service_version: ServiceVersion = request.match_info["service_version"]
        from_service_key: ServiceKey = request.query["fromService"]
        from_service_version: ServiceVersion = request.query["fromVersion"]
        from_output_key: ServiceOutputKey = request.query["fromOutput"]

    except (ValidationError, KeyError) as err:
        raise web.HTTPUnprocessableEntity() from err

    # Evaluate and return validated model
    response_model = await get_compatible_inputs_given_source_output(
        service_key,
        service_version,
        from_service_key,
        from_service_version,
        from_output_key,
    )

    # format response
    enveloped: str = json.dumps({"data": response_model})

    return web.Response(text=enveloped, content_type="application/json")


async def get_compatible_inputs_given_source_output(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    from_service_key: ServiceKey,
    from_service_version: ServiceVersion,
    from_output_key: ServiceOutputKey,
) -> List[ServiceInputKey]:
    """
        Filters inputs of this service that match a given service output

    Returns compatible input ports of the service, provided an output port of
    a connected node.

    """
    # TODO: uuid instead of key+version?

    return list()


@routes.get(
    "/catalog/services/{service_key:path}/{service_version}/outputs",
)
async def list_service_outputs_handler(request: Request):
    try:
        # match, parse and validate
        service_key: ServiceKey = request.match_info["service_key"]
        service_version: ServiceVersion = request.match_info["service_version"]

    except (ValidationError, KeyError) as err:
        raise web.HTTPUnprocessableEntity() from err

    # Evaluate and return validated model
    response_model = await list_service_outputs(service_key, service_version)

    # format response
    enveloped: str = json.dumps(
        {"data": [json.loads(m.json()) for m in response_model]}
    )

    return web.Response(text=enveloped, content_type="application/json")


async def list_service_outputs(
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> List[ServiceOutputApiOut]:
    # TODO: implement same call to catalog
    return list()


@routes.get(
    "/catalog/services/{service_key:path}/{service_version}/outputs/{output_key}"
)
async def get_service_output_handler(request: Request):
    try:
        # match, parse and validate
        service_key: ServiceKey = request.match_info["service_key"]
        service_version: ServiceVersion = request.match_info["service_version"]
        output_key: ServiceOutputKey = request.match_info["output_key"]

    except (ValidationError, KeyError) as err:
        raise web.HTTPUnprocessableEntity() from err

    # Evaluate and return validated model
    response_model = await get_service_output(service_key, service_version, output_key)

    # format response
    enveloped: str = json.dumps({"data": json.loads(response_model.json())})
    return web.Response(text=enveloped, content_type="application/json")


async def get_service_output(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    output_key: ServiceOutputKey,
) -> ServiceOutputApiOut:
    return ServiceInputApiOut()


@routes.get(
    "/catalog/services/{service_key:path}/{service_version}/outputs:match",
)
async def get_compatible_outputs_given_target_input_handler(request: Request):
    """
    Filters outputs of this service that match a given service input

    Returns compatible output port of a connected node for a given input
    """
    try:
        # match, parse and validate
        service_key: ServiceKey = request.match_info["service_key"]
        service_version: ServiceVersion = request.match_info["service_version"]
        to_service_key: ServiceKey = request.query["toService"]
        to_service_version: ServiceVersion = request.query["toVersion"]
        to_input_key: ServiceInputKey = request.query["toInput"]

    except (ValidationError, KeyError) as err:
        raise web.HTTPUnprocessableEntity() from err

    # Evaluate and return validated model
    response_model = await get_compatible_outputs_given_target_input(
        service_key,
        service_version,
        to_service_key,
        to_service_version,
        to_input_key,
    )

    # format response
    enveloped: str = json.dumps({"data": response_model})

    return web.Response(text=enveloped, content_type="application/json")


async def get_compatible_outputs_given_target_input(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    to_service_key: ServiceKey,
    to_service_version: ServiceVersion,
    to_input_key: ServiceInputKey,
) -> List[ServiceOutputKey]:

    return list()
