import logging
from collections.abc import Iterator
from typing import Any

from aiohttp import web
from aiohttp.web import Request
from models_library.api_schemas_webserver.catalog import (
    ServiceInputGet,
    ServiceInputKey,
    ServiceOutputGet,
    ServiceOutputKey,
)
from models_library.services import (
    ServiceInput,
    ServiceKey,
    ServiceOutput,
    ServiceVersion,
)
from models_library.users import UserID
from pint import UnitRegistry
from pydantic import BaseModel
from servicelib.aiohttp.requests_validation import handle_validation_as_http_error
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._constants import RQ_PRODUCT_KEY, RQT_USERID_KEY
from . import client
from ._api_units import can_connect, replace_service_input_outputs
from ._models import model_factory

_logger = logging.getLogger(__name__)


class CatalogRequestContext(BaseModel):
    app: web.Application
    user_id: UserID
    product_name: str
    unit_registry: UnitRegistry

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def create(cls, request: Request) -> "CatalogRequestContext":
        with handle_validation_as_http_error(
            error_msg_template="Invalid request",
            resource_name=request.rel_url.path,
            use_error_v1=True,
        ):
            assert request.app  # nosec
            return cls(
                app=request.app,
                user_id=request[RQT_USERID_KEY],
                product_name=request[RQ_PRODUCT_KEY],
                unit_registry=request.app[UnitRegistry.__name__],
            )


# IMPLEMENTATION --------------------------------------------------------------------------------


async def list_services(
    app: web.Application,
    user_id: UserID,
    product_name: str,
    unit_registry: UnitRegistry,
):
    services = await client.get_services_for_user_in_product(
        app, user_id, product_name, only_key_versions=False
    )
    for service in services:
        try:
            replace_service_input_outputs(
                service, unit_registry=unit_registry, **RESPONSE_MODEL_POLICY
            )
        except KeyError:  # noqa: PERF203
            # This will limit the effect of a any error in the formatting of
            # service metadata (mostly in label annotations). Otherwise it would
            # completely break all the listing operation. At this moment,
            # a limitation on schema's $ref produced an error that made faiing
            # the full service listing.
            _logger.exception(
                "Failed while processing this %s. "
                "Skipping service from listing. "
                "TIP: check formatting of docker label annotations for inputs/outputs.",
                f"{service=}",
            )
    return services


async def get_service(
    service_key: ServiceKey, service_version: ServiceVersion, ctx: CatalogRequestContext
) -> dict[str, Any]:
    service = await client.get_service(
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
    ctx: CatalogRequestContext,
):
    service = await client.update_service(
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
    service_key: ServiceKey, service_version: ServiceVersion, ctx: CatalogRequestContext
) -> list[ServiceInputGet]:
    service = await client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )
    inputs = []
    for input_key in service["inputs"]:
        service_input: ServiceInputGet = model_factory[
            ServiceInputGet
        ].from_catalog_service_api_model(service, input_key)
        inputs.append(service_input)
    return inputs


async def get_service_input(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    input_key: ServiceInputKey,
    ctx: CatalogRequestContext,
) -> ServiceInputGet:
    service = await client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )
    service_input: ServiceInputGet = model_factory[
        ServiceInputGet
    ].from_catalog_service_api_model(service, input_key)

    return service_input


async def get_compatible_inputs_given_source_output(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    from_service_key: ServiceKey,
    from_service_version: ServiceVersion,
    from_output_key: ServiceOutputKey,
    ctx: CatalogRequestContext,
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
    ctx: CatalogRequestContext,
) -> list[ServiceOutputGet]:
    service = await client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )

    outputs = []
    for output_key in service["outputs"]:
        service_output = model_factory[ServiceOutputGet].from_catalog_service_api_model(
            service, output_key
        )
        outputs.append(service_output)
    return outputs


async def get_service_output(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    output_key: ServiceOutputKey,
    ctx: CatalogRequestContext,
) -> ServiceOutputGet:
    service = await client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )
    service_output: ServiceOutputGet = model_factory[
        ServiceOutputGet
    ].from_catalog_service_api_model(service, output_key)

    return service_output


async def get_compatible_outputs_given_target_input(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    to_service_key: ServiceKey,
    to_service_version: ServiceVersion,
    to_input_key: ServiceInputKey,
    ctx: CatalogRequestContext,
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
