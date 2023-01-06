import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

import orjson
from aiohttp import web
from aiohttp.web import Request, RouteTableDef
from models_library.services import ServiceInput, ServiceOutput
from models_library.services_resources import (
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from pint import UnitRegistry
from pydantic import ValidationError
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from . import catalog_client
from ._constants import RQ_PRODUCT_KEY
from ._meta import api_version_prefix
from .catalog_models import (
    ServiceInputGet,
    ServiceInputKey,
    ServiceKey,
    ServiceOutputGet,
    ServiceOutputKey,
    ServiceVersion,
    json_dumps,
    replace_service_input_outputs,
)
from .catalog_units import can_connect
from .login.decorators import RQT_USERID_KEY, login_required
from .security_decorators import permission_required

logger = logging.getLogger(__name__)

###############
# API HANDLERS
#
# - TODO: uuid instead of key+version?
# - Take into account that part of the API is also needed in the public API so logic should
#   live in the catalog service in his final version
# TODO: define pruning of response policy: e.g. if None, send or not, if unset, send or not ...

VTAG = f"/{api_version_prefix}"


routes = RouteTableDef()


@dataclass
class _RequestContext:
    app: web.Application
    user_id: int
    product_name: str
    unit_registry: UnitRegistry

    @classmethod
    def create(cls, request: Request) -> "_RequestContext":
        return cls(
            app=request.app,
            user_id=request[RQT_USERID_KEY],
            product_name=request[RQ_PRODUCT_KEY],
            unit_registry=request.app[UnitRegistry.__name__],
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


@routes.get(f"{VTAG}/catalog/services")
@login_required
@permission_required("services.catalog.*")
async def list_services_handler(request: Request):
    with parameters_validation(request) as ctx:
        # match, parse and validate
        data_array = await list_services(ctx)

    enveloped: str = json_dumps({"data": data_array})
    return web.Response(text=enveloped, content_type="application/json")


@routes.get(f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}")
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


@routes.patch(f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}")
@login_required
@permission_required("services.catalog.*")
async def update_service_handler(request: Request):
    with parameters_validation(request) as ctx:
        # match, parse and validate
        service_key: ServiceKey = request.match_info["service_key"]
        service_version: ServiceVersion = request.match_info["service_version"]
        update_data: dict[str, Any] = await request.json(loads=orjson.loads)

    # Evaluate and return validated model
    data = await update_service(service_key, service_version, update_data, ctx)

    # format response
    enveloped: str = json_dumps({"data": data})
    return web.Response(text=enveloped, content_type="application/json")


@routes.get(f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/inputs")
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


@routes.get(
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/inputs/{{input_key}}"
)
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


@routes.get(f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/inputs:match")
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
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/outputs",
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
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/outputs/{{output_key}}"
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


@routes.get(
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/outputs:match"
)
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


@routes.get(f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/resources")
@login_required
@permission_required("services.catalog.*")
async def get_service_resources_handler(request: Request):
    """
    Filters outputs of this service that match a given service input

    Returns compatible output port of a connected node for a given input
    """
    with parameters_validation(request) as ctx:
        # match, parse and validate
        service_key: ServiceKey = request.match_info["service_key"]
        service_version: ServiceVersion = request.match_info["service_version"]

    service_resources: ServiceResourcesDict = (
        await catalog_client.get_service_resources(
            request.app,
            user_id=ctx.user_id,
            service_key=service_key,
            service_version=service_version,
        )
    )

    # format response
    enveloped: str = json_dumps(
        {"data": ServiceResourcesDictHelpers.create_jsonable(service_resources)}
    )
    return web.Response(text=enveloped, content_type="application/json")


###############
# IMPLEMENTATION
#


async def list_services(ctx: _RequestContext):
    services = await catalog_client.get_services_for_user_in_product(
        ctx.app, ctx.user_id, ctx.product_name, only_key_versions=False
    )
    for service in services:
        try:
            replace_service_input_outputs(
                service, unit_registry=ctx.unit_registry, **RESPONSE_MODEL_POLICY
            )
        except KeyError:
            # This will limit the effect of a any error in the formatting of
            # service metadata (mostly in label annotations). Otherwise it would
            # completely break all the listing operation. At this moment,
            # a limitation on schema's $ref produced an error that made faiing
            # the full service listing.
            logger.exception(
                "Failed while processing this %s. "
                "Skipping service from listing. "
                "TIP: check formatting of docker label annotations for inputs/outputs.",
                f"{service=}",
            )
    return services


async def get_service(
    service_key: ServiceKey, service_version: ServiceVersion, ctx: _RequestContext
) -> dict[str, Any]:
    service = await catalog_client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )
    replace_service_input_outputs(
        service, unit_registry=ctx.unit_registry, **RESPONSE_MODEL_POLICY
    )
    return service


async def update_service(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    update_data: dict[str, Any],
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
    replace_service_input_outputs(
        service, unit_registry=ctx.unit_registry, **RESPONSE_MODEL_POLICY
    )
    return service


async def list_service_inputs(
    service_key: ServiceKey, service_version: ServiceVersion, ctx: _RequestContext
) -> ServiceOutputGet:

    service = await catalog_client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )
    inputs = []
    for input_key in service["inputs"].keys():
        service_input = ServiceInputGet.from_catalog_service_api_model(
            service, input_key
        )
        inputs.append(service_input)
    return inputs


async def get_service_input(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    input_key: ServiceInputKey,
    ctx: _RequestContext,
) -> ServiceInputGet:

    service = await catalog_client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )
    service_input = ServiceInputGet.from_catalog_service_api_model(service, input_key)

    return service_input


async def get_compatible_inputs_given_source_output(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    from_service_key: ServiceKey,
    from_service_version: ServiceVersion,
    from_output_key: ServiceOutputKey,
    ctx: _RequestContext,
) -> list[ServiceInputKey]:
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

    def iter_service_inputs() -> Iterator[tuple[ServiceInputKey, ServiceInput]]:
        for service_input in service_inputs:
            yield service_input.key_id, ServiceInput.construct(
                **service_input.dict(include=ServiceInput.__fields__.keys())
            )

    # check
    matches = []
    for key_id, to_input in iter_service_inputs():
        if can_connect(from_output, to_input, units_registry=ctx.unit_registry):
            matches.append(key_id)

    return matches


async def list_service_outputs(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    ctx: _RequestContext,
) -> list[ServiceOutputGet]:
    service = await catalog_client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )

    outputs = []
    for output_key in service["outputs"].keys():
        service_output = ServiceOutputGet.from_catalog_service_api_model(
            service, output_key
        )
        outputs.append(service_output)
    return outputs


async def get_service_output(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    output_key: ServiceOutputKey,
    ctx: _RequestContext,
) -> ServiceOutputGet:
    service = await catalog_client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )
    service_output = ServiceOutputGet.from_catalog_service_api_model(
        service, output_key
    )

    return service_output


async def get_compatible_outputs_given_target_input(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    to_service_key: ServiceKey,
    to_service_version: ServiceVersion,
    to_input_key: ServiceInputKey,
    ctx: _RequestContext,
) -> list[ServiceOutputKey]:

    # N outputs
    service_outputs = await list_service_outputs(service_key, service_version, ctx)

    def iter_service_outputs() -> Iterator[tuple[ServiceOutputKey, ServiceOutput]]:
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
        if can_connect(from_output, to_input, units_registry=ctx.unit_registry):
            matches.append(key_id)

    return matches
