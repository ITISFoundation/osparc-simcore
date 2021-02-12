import json
from dataclasses import dataclass
from typing import Iterator, List, Tuple

from aiohttp import web
from aiohttp.web import Request, RouteTableDef
from models_library.services import ServiceInput, ServiceOutput
from pydantic import ValidationError

from . import catalog_client
from .catalog_api_models import (
    ServiceInputApiOut,
    ServiceInputKey,
    ServiceKey,
    ServiceOutputApiOut,
    ServiceOutputKey,
    ServiceVersion,
)
from .constants import RQ_PRODUCT_KEY
from .login.decorators import RQT_USERID_KEY, login_required
from .security_decorators import permission_required

###############
# API HANDLERS
#
# - TODO: uuid instead of key+version?
# - Take into account that part of the API is also needed in the public API so logic should
#   live in the catalog service in his final version

routes = RouteTableDef()


@dataclass
class _RequestContext:
    app: web.Application
    user_id: int
    product_name: str

    @classmethod
    def create(cls, request: Request) -> "_RequestContext":
        return cls(
            app=request.app,
            user_id=request[RQT_USERID_KEY],
            product_name=request[RQ_PRODUCT_KEY],
        )


@routes.get("/catalog/services/{service_key:path}/{service_version}/inputs")
@login_required
@permission_required("services.catalog.*")
async def list_service_inputs_handler(request: Request):
    try:
        # match, parse and validate
        service_key: ServiceKey = request.match_info["service_key"]
        service_version: ServiceVersion = request.match_info["service_version"]

    except (ValidationError, KeyError) as err:
        # TODO: convert into HTTP validation error
        raise web.HTTPUnprocessableEntity() from err

    # Evaluate and return validated model
    response_model = await list_service_inputs(
        service_key, service_version, _RequestContext.create(request)
    )

    # format response
    enveloped: str = json.dumps(
        {"data": [json.loads(m.json()) for m in response_model]}
    )

    return web.Response(text=enveloped, content_type="application/json")


@routes.get("/catalog/services/{service_key:path}/{service_version}/inputs/{input_key}")
@login_required
@permission_required("services.catalog.*")
async def get_service_input_handler(request: Request):
    try:
        # match, parse and validate
        service_key: ServiceKey = request.match_info["service_key"]
        service_version: ServiceVersion = request.match_info["service_version"]
        input_key: ServiceInputKey = request.match_info["input_key"]

    except (ValidationError, KeyError) as err:
        raise web.HTTPUnprocessableEntity() from err

    # Evaluate and return validated model
    response_model = await get_service_input(
        service_key, service_version, input_key, _RequestContext.create(request)
    )

    # format response
    enveloped: str = json.dumps({"data": json.loads(response_model.json())})
    return web.Response(text=enveloped, content_type="application/json")


@routes.get("/catalog/services/{service_key:path}/{service_version}/inputs:match")
@login_required
@permission_required("services.catalog.*")
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
        _RequestContext.create(request),
    )

    # format response
    enveloped: str = json.dumps({"data": response_model})

    return web.Response(text=enveloped, content_type="application/json")


@routes.get(
    "/catalog/services/{service_key:path}/{service_version}/outputs",
)
@login_required
@permission_required("services.catalog.*")
async def list_service_outputs_handler(request: Request):
    try:
        # match, parse and validate
        service_key: ServiceKey = request.match_info["service_key"]
        service_version: ServiceVersion = request.match_info["service_version"]

    except (ValidationError, KeyError) as err:
        raise web.HTTPUnprocessableEntity() from err

    # Evaluate and return validated model
    response_model = await list_service_outputs(
        service_key, service_version, _RequestContext.create(request)
    )

    # format response
    enveloped: str = json.dumps(
        {"data": [json.loads(m.json()) for m in response_model]}
    )

    return web.Response(text=enveloped, content_type="application/json")


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
    response_model = await get_service_output(
        service_key, service_version, output_key, _RequestContext.create(request)
    )

    # format response
    enveloped: str = json.dumps({"data": json.loads(response_model.json())})
    return web.Response(text=enveloped, content_type="application/json")


@routes.get("/catalog/services/{service_key:path}/{service_version}/outputs:match")
@login_required
@permission_required("services.catalog.*")
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
        _RequestContext.create(request),
    )

    # format response
    enveloped: str = json.dumps({"data": response_model})

    return web.Response(text=enveloped, content_type="application/json")


###############
# IMPLEMENTATION
#


def can_connect(from_output: ServiceOutput, to_input: ServiceInput) -> bool:
    # FIXME: can_connect is a very very draft version

    # compatible units
    ok = from_output.unit == to_input.unit
    if ok:
        # compatible types TODO: see mimetypes examples in property_type
        ok = from_output.property_type == to_input.property_type
        if not ok:
            ok = "data:*/*" in (from_output.property_type, to_input.property_type)
    return ok


async def list_service_inputs(
    service_key: ServiceKey, service_version: ServiceVersion, ctx: _RequestContext
) -> List[ServiceOutputApiOut]:

    service = await catalog_client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )

    inputs = []
    for input_key in service["inputs"].keys():
        service_input = ServiceInputApiOut.from_service(service, input_key)
        inputs.append(service_input)
    return inputs


async def get_service_input(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    input_key: ServiceInputKey,
    ctx: _RequestContext,
) -> ServiceInputApiOut:

    service = await catalog_client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )
    service_input = ServiceInputApiOut.from_service(service, input_key)

    return service_input


async def get_compatible_inputs_given_source_output(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    from_service_key: ServiceKey,
    from_service_version: ServiceVersion,
    from_output_key: ServiceOutputKey,
    ctx: _RequestContext,
) -> List[ServiceInputKey]:
    """
        Filters inputs of this service that match a given service output

    Returns keys of compatible input ports of the service, provided an output port of
    a connected node.
    """

    # 1 output
    service_output = await get_service_output(
        from_service_key, from_service_version, from_output_key, ctx
    )
    from_output: ServiceOutput = ServiceOutput.construct(
        **service_output.dict(include=ServiceOutput.__fields_set__)
    )

    # N inputs
    service_inputs = await list_service_inputs(service_key, service_version, ctx)

    def iter_service_inputs() -> Iterator[Tuple[ServiceInputKey, ServiceInput]]:
        for service_input in service_inputs:
            yield service_input.key_id, ServiceInput.construct(
                **service_input.dict(include=ServiceInput.__fields_set__)
            )

    # check
    matches = []
    for key_id, to_input in iter_service_inputs():
        if can_connect(from_output, to_input):
            matches.append(key_id)

    return matches


async def list_service_outputs(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    ctx: _RequestContext,
) -> List[ServiceOutputApiOut]:
    service = await catalog_client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )

    outputs = []
    for output_key in service["outputs"].keys():
        service_output = ServiceOutputApiOut.from_service(service, output_key)
        outputs.append(service_output)
    return outputs


async def get_service_output(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    output_key: ServiceOutputKey,
    ctx: _RequestContext,
) -> ServiceOutputApiOut:
    service = await catalog_client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )
    service_output = ServiceOutputApiOut.from_service(service, output_key)

    return service_output


async def get_compatible_outputs_given_target_input(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    to_service_key: ServiceKey,
    to_service_version: ServiceVersion,
    to_input_key: ServiceInputKey,
    ctx: _RequestContext,
) -> List[ServiceOutputKey]:

    # N outputs
    service_outputs = await list_service_outputs(service_key, service_version, ctx)

    def iter_service_outputs() -> Iterator[Tuple[ServiceOutputKey, ServiceOutput]]:
        for service_output in service_outputs:
            yield service_output.key_id, ServiceOutput.construct(
                **service_output.dict(include=ServiceOutput.__fields_set__)
            )

    # 1 input
    service_input = await get_service_input(
        to_service_key, to_service_version, to_input_key, ctx
    )
    to_input: ServiceInput = ServiceInput.construct(
        **service_input.dict(include=ServiceInput.__fields_set__)
    )

    # check
    matches = []
    for key_id, from_output in iter_service_outputs():
        if can_connect(from_output, to_input):
            matches.append(key_id)

    return matches
