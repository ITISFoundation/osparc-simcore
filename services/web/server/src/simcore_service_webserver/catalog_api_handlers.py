from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Tuple

import orjson
from aiohttp import web
from aiohttp.web import Request, RouteTableDef
from models_library.services import ServiceInput, ServiceOutput
from pydantic import ValidationError

from . import catalog_client
from ._meta import api_version_prefix
from .catalog_api_models import (
    ServiceInputApiOut,
    ServiceInputKey,
    ServiceKey,
    ServiceOutputApiOut,
    ServiceOutputKey,
    ServiceVersion,
    json_dumps,
    replace_service_input_outputs,
)
from .constants import RQ_PRODUCT_KEY
from .login.decorators import RQT_USERID_KEY, login_required
from .rest_utils import RESPONSE_MODEL_POLICY
from .security_decorators import permission_required

###############
# API HANDLERS
#
# - TODO: uuid instead of key+version?
# - Take into account that part of the API is also needed in the public API so logic should
#   live in the catalog service in his final version
# TODO: define pruning of response policy: e.g. if None, send or not, if unset, send or not ...

VX = f"/{api_version_prefix}"


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


@contextmanager
def parameters_validation(request: web.Request):
    """Context manager to wrap match, parsing and validation of
    request parameters (both path and queries)
    """
    try:
        try:
            context = _RequestContext.create(request)
        except KeyError as err:
            raise web.HTTPBadRequest(reason="Invalid headers") from err

        yield context

        #
        # wraps match, parse and validate
        # For instance
        #   service_key: ServiceKey = request.match_info["service_key"]
        #   from_service_version: ServiceVersion = request.query["fromVersion"]
        #   body = await request.json()
        #
    except ValidationError as err:
        raise web.HTTPUnprocessableEntity(
            text=json_dumps({"error": err.errors()}), content_type="application/json"
        ) from err

    except KeyError as err:
        raise web.HTTPBadRequest(reason=f"Expected parameter {err}") from err


@routes.get(VX + "/catalog/services")
@login_required
@permission_required("services.catalog.*")
async def list_services_handler(request: Request):
    with parameters_validation(request) as ctx:
        # match, parse and validate
        data_array = await list_services(ctx)

    enveloped: str = json_dumps({"data": data_array})
    return web.Response(text=enveloped, content_type="application/json")


@routes.get(VX + "/catalog/services/{service_key}/{service_version}")
@login_required
@permission_required("services.catalog.*")
async def get_service_handler(request: Request):
    with parameters_validation(request) as ctx:
        # match, parse and validate
        service_key: ServiceKey = request.match_info["service_key"]
        service_version: ServiceVersion = request.match_info["service_version"]

    # Evaluate and return validated model
    data = await get_service(service_key, service_version, ctx)

    # format response
    enveloped: str = json_dumps({"data": data})
    return web.Response(text=enveloped, content_type="application/json")


@routes.patch(VX + "/catalog/services/{service_key}/{service_version}")
@login_required
@permission_required("services.catalog.*")
async def update_service_handler(request: Request):
    with parameters_validation(request) as ctx:
        # match, parse and validate
        service_key: ServiceKey = request.match_info["service_key"]
        service_version: ServiceVersion = request.match_info["service_version"]
        update_data: Dict[str, Any] = await request.json(loads=orjson.loads)

    # Evaluate and return validated model
    data = await update_service(service_key, service_version, update_data, ctx)

    # format response
    enveloped: str = json_dumps({"data": data})
    return web.Response(text=enveloped, content_type="application/json")


@routes.get(VX + "/catalog/services/{service_key}/{service_version}/inputs")
@login_required
@permission_required("services.catalog.*")
async def list_service_inputs_handler(request: Request):
    with parameters_validation(request) as ctx:
        # match, parse and validate
        service_key: ServiceKey = request.match_info["service_key"]
        service_version: ServiceVersion = request.match_info["service_version"]

    # Evaluate and return validated model
    response_model = await list_service_inputs(service_key, service_version, ctx)

    # format response
    enveloped: str = json_dumps(
        {"data": [m.dict(**RESPONSE_MODEL_POLICY) for m in response_model]}
    )
    return web.Response(text=enveloped, content_type="application/json")


@routes.get(VX + "/catalog/services/{service_key}/{service_version}/inputs/{input_key}")
@login_required
@permission_required("services.catalog.*")
async def get_service_input_handler(request: Request):
    with parameters_validation(request) as ctx:
        # match, parse and validate
        service_key: ServiceKey = request.match_info["service_key"]
        service_version: ServiceVersion = request.match_info["service_version"]
        input_key: ServiceInputKey = request.match_info["input_key"]

    # Evaluate and return validated model
    response_model = await get_service_input(
        service_key, service_version, input_key, ctx
    )

    # format response
    enveloped: str = json_dumps({"data": response_model.dict(**RESPONSE_MODEL_POLICY)})
    return web.Response(text=enveloped, content_type="application/json")


@routes.get(VX + "/catalog/services/{service_key}/{service_version}/inputs:match")
@login_required
@permission_required("services.catalog.*")
async def get_compatible_inputs_given_source_output_handler(request: Request):
    with parameters_validation(request) as ctx:
        # match, parse and validate
        service_key: ServiceKey = request.match_info["service_key"]
        service_version: ServiceVersion = request.match_info["service_version"]
        from_service_key: ServiceKey = request.query["fromService"]
        from_service_version: ServiceVersion = request.query["fromVersion"]
        from_output_key: ServiceOutputKey = request.query["fromOutput"]

    # Evaluate and return validated model
    data = await get_compatible_inputs_given_source_output(
        service_key,
        service_version,
        from_service_key,
        from_service_version,
        from_output_key,
        ctx,
    )

    # format response
    enveloped: str = json_dumps({"data": data})
    return web.Response(text=enveloped, content_type="application/json")


@routes.get(
    VX + "/catalog/services/{service_key}/{service_version}/outputs",
)
@login_required
@permission_required("services.catalog.*")
async def list_service_outputs_handler(request: Request):
    with parameters_validation(request) as ctx:
        # match, parse and validate
        service_key: ServiceKey = request.match_info["service_key"]
        service_version: ServiceVersion = request.match_info["service_version"]

    # Evaluate and return validated model
    response_model = await list_service_outputs(service_key, service_version, ctx)

    # format response
    enveloped: str = json_dumps(
        {"data": [m.dict(**RESPONSE_MODEL_POLICY) for m in response_model]}
    )
    return web.Response(text=enveloped, content_type="application/json")


@routes.get(
    VX + "/catalog/services/{service_key}/{service_version}/outputs/{output_key}"
)
@login_required
@permission_required("services.catalog.*")
async def get_service_output_handler(request: Request):
    with parameters_validation(request) as ctx:
        # match, parse and validate
        service_key: ServiceKey = request.match_info["service_key"]
        service_version: ServiceVersion = request.match_info["service_version"]
        output_key: ServiceOutputKey = request.match_info["output_key"]

    # Evaluate and return validated model
    response_model = await get_service_output(
        service_key, service_version, output_key, ctx
    )

    # format response
    enveloped: str = json_dumps({"data": response_model.dict(**RESPONSE_MODEL_POLICY)})
    return web.Response(text=enveloped, content_type="application/json")


@routes.get(VX + "/catalog/services/{service_key}/{service_version}/outputs:match")
@login_required
@permission_required("services.catalog.*")
async def get_compatible_outputs_given_target_input_handler(request: Request):
    """
    Filters outputs of this service that match a given service input

    Returns compatible output port of a connected node for a given input
    """
    with parameters_validation(request) as ctx:
        # match, parse and validate
        service_key: ServiceKey = request.match_info["service_key"]
        service_version: ServiceVersion = request.match_info["service_version"]
        to_service_key: ServiceKey = request.query["toService"]
        to_service_version: ServiceVersion = request.query["toVersion"]
        to_input_key: ServiceInputKey = request.query["toInput"]

    # Evaluate and return validated model
    data = await get_compatible_outputs_given_target_input(
        service_key,
        service_version,
        to_service_key,
        to_service_version,
        to_input_key,
        ctx,
    )

    # format response
    enveloped: str = json_dumps({"data": data})
    return web.Response(text=enveloped, content_type="application/json")


###############
# IMPLEMENTATION
#


def can_connect(from_output: ServiceOutput, to_input: ServiceInput) -> bool:
    # FIXME: can_connect is a very very draft version

    # compatible units
    ok = from_output.unit == to_input.unit
    if ok:
        # compatible types
        # FIXME: see mimetypes examples in property_type
        #
        #   "pattern": "^(number|integer|boolean|string|data:([^/\\s,]+/[^/\\s,]+|\\[[^/\\s,]+/[^/\\s,]+(,[^/\\s]+/[^/,\\s]+)*\\]))$",
        #   "description": "data type expected on this input glob matching for data type is allowed",
        #   "examples": [
        #     "number",
        #     "boolean",
        #     "data:*/*",
        #     "data:text/*",
        #     "data:[image/jpeg,image/png]",
        #     "data:application/json",
        #     "data:application/json;schema=https://my-schema/not/really/schema.json",
        #     "data:application/vnd.ms-excel",
        #     "data:text/plain",
        #     "data:application/hdf5",
        #     "data:application/edu.ucdavis@ceclancy.xyz"
        #
        ok = from_output.property_type == to_input.property_type
        if not ok:
            ok = (
                to_input.property_type == "data:*/*"
                and from_output.property_type.startswith("data:")
            )
    return ok


async def list_services(ctx: _RequestContext):
    services = await catalog_client.get_services_for_user_in_product(
        ctx.app, ctx.user_id, ctx.product_name, only_key_versions=False
    )
    for service in services:
        replace_service_input_outputs(service, **RESPONSE_MODEL_POLICY)
    return services


async def get_service(
    service_key: ServiceKey, service_version: ServiceVersion, ctx: _RequestContext
) -> Dict[str, Any]:
    service = await catalog_client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )
    replace_service_input_outputs(service, **RESPONSE_MODEL_POLICY)
    return service


async def update_service(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    update_data: Dict[str, Any],
    ctx: _RequestContext,
):
    service = await catalog_client.update_service(
        ctx.app,
        ctx.user_id,
        service_key,
        service_version,
        ctx.product_name,
        update_data,
    )
    replace_service_input_outputs(service, **RESPONSE_MODEL_POLICY)
    return service


async def list_service_inputs(
    service_key: ServiceKey, service_version: ServiceVersion, ctx: _RequestContext
) -> List[ServiceOutputApiOut]:

    service = await catalog_client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )

    inputs = []
    for input_key in service["inputs"].keys():
        service_input = ServiceInputApiOut.from_catalog_service(service, input_key)
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
    service_input = ServiceInputApiOut.from_catalog_service(service, input_key)

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
        **service_output.dict(include=ServiceOutput.__fields__.keys())
    )

    # N inputs
    service_inputs = await list_service_inputs(service_key, service_version, ctx)

    def iter_service_inputs() -> Iterator[Tuple[ServiceInputKey, ServiceInput]]:
        for service_input in service_inputs:
            yield service_input.key_id, ServiceInput.construct(
                **service_input.dict(include=ServiceInput.__fields__.keys())
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
        service_output = ServiceOutputApiOut.from_catalog_service(service, output_key)
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
    service_output = ServiceOutputApiOut.from_catalog_service(service, output_key)

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
                **service_output.dict(include=ServiceOutput.__fields__.keys())
            )

    # 1 input
    service_input = await get_service_input(
        to_service_key, to_service_version, to_input_key, ctx
    )
    to_input: ServiceInput = ServiceInput.construct(
        **service_input.dict(include=ServiceInput.__fields__.keys())
    )

    # check
    matches = []
    for key_id, from_output in iter_service_outputs():
        if can_connect(from_output, to_input):
            matches.append(key_id)

    return matches
